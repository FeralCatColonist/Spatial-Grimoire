import argparse
import os
import subprocess
from pathlib import Path

# Variables
WebGISDR_filename = "webgisdr"
WebGISDR_dir = Path(r"C:\Program Files\ArcGIS\Portal\tools\webgisdr")
WebGISDR_backups_path = Path(r"\\some-filepath-here")
spacer = "-" * 50


def prune_copies(webgisdr_backups_path: Path, backup_arguments: argparse.Namespace):
    """Prunes a list of files according to the number of copies.

    Args:
        webgisdr_backups_path (Path): a directory path to the .webgissite backups
        backup_arguments (argparse.Namespace): the user input arguments for backup and copies
    """
    print(f"Pruning backups")
    WebGISDR_backups = list(
        webgisdr_backups_path.glob(f"*{backup_arguments.mode}.webgissite")
    )
    WebGISDR_backups.sort(reverse=True)
    file_names = [file.name for file in WebGISDR_backups]
    backups_retained = file_names[: backup_arguments.copies]
    backups_pruned = [item for item in file_names if item not in backups_retained]
    for file in backups_pruned:
        Path(webgisdr_backups_path, file).unlink()
    print(f"\tretained:\t{backups_retained}\n\tpruned:\t\t{backups_pruned}\n")
    return


def set_WebGISDR(webgisdr_dir: Path, webgisdr_filename: str, backup_mode: str):
    """Sets the WebGISDR configuration file's BACKUP_RESTORE_MODE property

    Args:
        webgisdr_dir (Path): the webgisdr tools directory path on the arcgisportal machine
        webgisdr_filename (str): the name of your webgisdr configuration file, it is normally 'webgisdr'
        backup_mode (str): the backup mode that was input as an argument
    """
    print(f"Setting {webgisdr_filename}.properties: BACKUP_RESTORE_MODE")
    WebGISDR_properties = Path(webgisdr_dir, f"{webgisdr_filename}.properties")
    file_content = WebGISDR_properties.read_text()
    lines = [line for line in file_content.splitlines()]
    for i, line in enumerate(lines):
        if "BACKUP_RESTORE_MODE =" in line:
            print(f"\tcurrent value:\t{line.split(' = ')[-1]}")
            lines[i] = f"BACKUP_RESTORE_MODE = {backup_mode}"
    WebGISDR_properties.write_text("\n".join(lines))
    print(f"\tset value:\t{backup_mode}\n")
    return


def run_WebGISDR(webgisdr_dir: Path, webgisdr_filename: str):
    """Runs the WebGISDR command-line utility

    Args:
        webgisdr_dir (Path): the webgisdr tools directory path on the arcgisportal machine
        webgisdr_filename (str): the name of your webgisdr configuration file, it is normally 'webgisdr'
    """
    print(
        f"Changing Directory to {webgisdr_dir}\n\trunning standard WebGISDR utility now\n\n{spacer}\n{spacer}"
    )
    os.chdir(webgisdr_dir)
    cmd_webgisdr = f"webgisdr --export --file {webgisdr_filename}.properties"
    subprocess.run(cmd_webgisdr, shell=True)
    print(f"{spacer}\n{spacer}\nAll Operations Complete\n{spacer}\n{spacer}")
    return


def configure():
    """Configures the user input arguments

    Returns:
        argparse.Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["FULL", "INCREMENTAL", "BACKUP"],
        type=str.upper,
        help="""the type of WebGISDR backup to be performed: backup, full, or
        incremental. this input is case insensitive.
        """,
    )
    parser.add_argument(
        "copies",
        choices=range(1, 8),
        type=int,
        help="""
        the number of copies to retain. this is the number of backups
        only for the backup mode input/selected. this is exclusive of the primary backup
        which will run at the end of the script.
        """,
    )
    print(f"{spacer}\n{spacer}\nRunning WebGISDR Automation")
    return parser.parse_args()


def main(backup_arguments: argparse.Namespace):
    print(
        f"\tbackup_mode is: {backup_arguments.mode}\n\tcopies to retain: {backup_arguments.copies}\n"
    )
    prune_copies(WebGISDR_backups_path, backup_arguments)
    set_WebGISDR(WebGISDR_dir, WebGISDR_filename, backup_arguments.mode)
    run_WebGISDR(WebGISDR_dir, WebGISDR_filename)


if __name__ == "__main__":
    arguments = configure()
    main(arguments)
