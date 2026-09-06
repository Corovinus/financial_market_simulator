"""Extract the image using an existing 7-Zip installation (7z or 7zz)."""
import argparse
import shutil
import subprocess
from pathlib import Path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    executable = shutil.which('7z') or shutil.which('7zz')
    if executable is None:
        parser.error('Install 7-Zip (7z/7zz); extracted files are already included.')
    if not args.image.is_file():
        parser.error('Image does not exist')
    if args.destination.exists() and any(args.destination.iterdir()):
        parser.error('Use an empty destination to preserve existing files.')
    subprocess.run([executable, 'x', str(args.image.resolve()),
                    '-o' + str(args.destination.resolve()), '-y'], check=True)
