import click
import pycurl

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


@click.group()
def setup():
    pass

    
BUILD_DIR = Path("gcc_build")


BINUTILS_NAME = 'binutils-2.42'
BINUTILS_EXT  =               '.tar.xz'
BINUTILS_URL  = 'http://ftp.gnu.org/gnu/binutils/' + BINUTILS_NAME + BINUTILS_EXT
def build_binutils(prefix, target, quiet):
    subprocess.run(["../configure",
                    f"--target={target}",
                    f"--prefix={prefix}",
                    "--disable-werror",
                    "--with-sysroot",
                    "--disable-nls", quiet], check=True)
    subprocess.run(["make", quiet], check=True)
    subprocess.run(["make install", quiet], check=True)    

GCC_NAME = 'gcc-13.2.0'
GCC_EXT  =            '.tar.gz'
GCC_URL  = 'http://ftp.gnu.org/gnu/gcc/' + GCC_NAME + '/' + GCC_NAME + GCC_EXT
def build_gcc(prefix, target, quiet):
    subprocess.run(["../configure",
                    f"--target={target}",
                    f"--prefix={prefix}",
                    "--disable-nls",
                    "--enable-languages=c,c++",
                    "--without-headers", quiet], check=True)
    subprocess.run(["make all-gcc", quiet], check=True)
    subprocess.run(["make all-target-libgcc", quiet], check=True)
    subprocess.run(["make install-gcc", quiet], check=True)
    subprocess.run(["make install-target-libgcc", quiet], check=True)

class Archive:
    def __init__(self, name, ext, url, build):
        self.name  = name
        self.ext   = ext
        self.url   = url
        self.build = build

archives = [
    Archive(BINUTILS_NAME,  BINUTILS_EXT,  BINUTILS_URL,  build_binutils),
    Archive(GCC_NAME,       GCC_EXT,       GCC_URL,       build_gcc)
]


@setup.command(help='Cleans source directories (make clean).')
def clean():
    try:
        os.chdir(BUILD_DIR)

        for archive in archives:
            if click.confirm(f">>> Cleaning {archive.name}. Are you sure?"):
                try:
                    os.chdir(f"{archive.name}/build")
                    subprocess.run(["make", "clean"], check=True)
                    os.chdir("../..")
                except subprocess.CalledProcessError:
                    print(f"!!! Exiting {archive.name}.")
                except FileNotFoundError:
                    print(f"!!! {BUILD_DIR}/{archive.name}/build doesn't exist.")

    except FileNotFoundError:
        print(f"!!! {BUILD_DIR} doesn't exist. Did you run install-gcc command?")

    os.chdir("..")

        
def download_progress_bar(downloadTotal, downloaded, uploadTotal, uploaded):
    progressBar = click.progressbar(
        length=downloadTotal,
        show_percent=True,
        show_eta=True
    )
    progressBar.update(downloaded)

def download_archives():
    curl = pycurl.Curl()
    curl.setopt(curl.NOPROGRESS,       False)
    curl.setopt(curl.XFERINFOFUNCTION, download_progress_bar)

    try:
        for archive in archives:
            archiveName = archive.name + archive.ext
            if os.path.isfile(archiveName):
                print(f">>> {archiveName} exists. Continuing...")
                continue
            
            archiveFile = open(archiveName, "wb")

            curl.setopt(curl.URL,       archive.url)
            curl.setopt(curl.WRITEDATA, archiveFile)
            print(f'>>> Downloading {archiveName}...')
            curl.perform()
            print()

            archiveFile.close()
            
    except pycurl.error as error:
        print(f'\n!!! PycURL error: {error}')
            
    curl.close()
    
dependencies = ['bison', 'flex', 'make']

def check_dependencies():
    try:
        for executable in dependencies:
            print(f">>> Checking for {executable}.")
            subprocess.run([executable, "--version"])
            
    except FileNotFoundError:
        print(f"!!! {executable} is required.")
        exit(0)

def extract_sources():
    print(">>> Extracting files...")
    for archive in archives:
        if os.path.isdir(archive.name):
            print(f">>> {archive.name} exists. Continuing...")
            continue
        
        tar = tarfile.open(archive.name + archive.ext)
        tar.extractall(numeric_owner=True)
    
@setup.command(help='Installs gcc cross compiler (type install-gcc --help for options).')
@click.argument('prefix', envvar='PREFIX', type=click.Path())
@click.argument('target', envvar='TARGET')
@click.option('--ignore-installed', help="Ignores installed cross compiler.", is_flag=True)
@click.option('--quiet', help="Doesn't output make commands.", is_flag=True)
def install_gcc(prefix, target, ignore_installed, quiet):
    if not ignore_installed:
        try:
            subprocess.run(f"{target}-gcc", check=True)
        except subprocess.CalledProcessError:
            print(f">>> {target}-gcc is already installed.")
            exit(0)
    else:
        if not click.confirm(f">>> Ignoring installed {target}-gcc. Are you sure"):
            exit(0)

    BUILD_DIR.mkdir(exist_ok=True)
    
    print(f'>>> Entering {BUILD_DIR}.')
    os.chdir(BUILD_DIR)
    
    check_dependencies()
    download_archives()
    extract_sources()

    sys.path += [f"{prefix}/bin"]
    for archive in archives:
        os.chdir(archive.name)
        print(f'>>> Building {archive.name}...')

        buildDir = Path('build')
        buildDir.mkdir(exist_ok=True)
        os.chdir(buildDir)

        quiet = "--quiet" if quiet else ""
        try:
            archive.build(prefix, target, quiet)
        except subprocess.CalledProcessError:
            print(f"!!! Exiting.")
            exit(1)
            
        print(f'>>> Built {archive.name}, no errors. Exiting.')
        os.chdir("../..")

    print(f'>>> Finished. Exiting {BUILD_DIR}.')
    os.chdir("..")
    

if __name__ == '__main__':
    print("GCC cross-compiler installer\n")
    setup()
    exit(0)
