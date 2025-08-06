"""
ArcGIS Patch Notifier.

This script checks for new ArcGIS patches by comparing local and online patch manifests.
When new patches are found, it sends email notifications to specified recipients.

Constants:
    ARCGIS_PATCHES_FILE: Path to the local patches JSON file
    ESRI_PATCHES_URL: URL to the ESRI patches JSON
    ARCGIS_VERSIONS: List of ArcGIS versions to check for patches
    MESSAGE_RECIPIENTS: List of email addresses to notify
"""

import json
import logging
import os
import pathlib
import smtplib
from email.message import EmailMessage

import requests

ARCGIS_PATCHES_FILE = pathlib.Path("arcgis-patches.json")
ESRI_PATCHES_URL = "https://downloads.esri.com/patch_notification/patches.json"
ARCGIS_VERSIONS = ["11.2"]
MESSAGE_RECIPIENTS = [
    "your-email-here",
]


def configure_logger(file_path: pathlib.Path):
    """a convenience function for configuring a logger

    Required Parameters:
        file_path:pathlib.Path | expects a Path object

    """
    os.chdir(file_path.parent)
    logging.basicConfig(
        filename=f"{file_path.stem}.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


current_file = pathlib.Path(__file__).resolve()
configure_logger(current_file)


def send_email(
    msg_subject: str,
    msg_content: str,
    msg_to: list[str],
    msg_from: str = "email-is-from@.com-or-whatever",
    msg_cc: list[str] = [""],
    msg_bcc: list[str] = [""],
    msg_priority: int = 3,
):
    """This is an email helper function, it accepts the standard parameters from email.message

    Required Parameters:
        msg_subject:str | a string representing the messge subject line
        msg_content:str | a string representing the message content
        msg_to:list[str] | a list of strings representing email addresses, as "To" email recipients

    Optional Parameters:
        msg_from:str |  a string representing the messager sender, optional, has a default value
        msg_cc:list[str] |  a list of strings representing email addresses, as "Cc" email recipients, optional
        msg_bcc:list[str] | a list of strings representing email addresses, as "Bcc" email recipients, optional
        msg_priority:int | a value between 1-5, 1 being the highest priority and 5 being the lowest, the default is 3

    Returns:
        None
    """
    message = EmailMessage()
    message["Subject"] = msg_subject
    message["From"] = msg_from
    message["To"] = ", ".join(msg_to)
    message["X-Priority"] = str(msg_priority)
    if msg_cc != [""]:
        message["Cc"] = ", ".join(msg_cc)
    if msg_bcc != [""]:
        message["Bcc"] = ", ".join(msg_bcc)
    message.set_content(msg_content)

    smtp_server = smtplib.SMTP(
        "your-smtp-info", port=999
    )  # change to your SMTP server and port
    smtp_server.send_message(message)
    smtp_server.quit()

    return None


def find_product(product_version: list[str], patch_json: dict) -> dict:
    """
    Extract patches for specific product versions from the complete patch JSON.

    Args:
        product_version: List of version strings to filter by (e.g. ["11.2", "11.3"])
        patch_json: Complete patch data JSON dictionary from ESRI

    Returns:
        Dictionary mapping version strings to their respective patch lists, each
        patch is represented by a dictionary containing patch details

    Example:
        {"11.2": [{patch1}, {patch2}], "11.3": [{patch3}, {patch4}]}
    """
    available_patches = {}
    for item in patch_json["Product"]:
        if item["version"] in product_version:
            available_patches[item["version"]] = item["patches"]
    return available_patches


def format_patch_differences(patches_local: dict, patches_online: dict) -> str:
    """
    Format the differences between local and online patches into a readable string.

    Compares patches in online manifest that aren't in the local manifest and
    formats them into a human-readable format suitable for email notifications.

    Args:
        patches_local: Dictionary of local patches indexed by version
        patches_online: Dictionary of online patches indexed by version

    Returns:
        Formatted string with details of new patches
    """
    formatted_patches = []
    for version, online_patches in patches_online.items():
        for patch in online_patches:
            if patch not in patches_local[version]:
                logging.info(f"\tnew patch found for version: {version} - {patch}")
                formatted_patches.append(f"- Version: {version} | {patch['Name']}")
                formatted_patches.append(f"\t- Product: {patch['Products']}")
                formatted_patches.append(f"\t- Release Date: {patch['ReleaseDate']}")
                formatted_patches.append(f"\t- Critical: {patch['Critical']}\n")
    return "\n".join(formatted_patches)


def get_local_patches(local_patches_path: pathlib.Path) -> dict:
    """
    Retrieve patch information from local manifest or download if not available.

    If the local manifest file exists, reads and parses it.
    Otherwise, downloads the manifest from ESRI and saves it locally.

    Args:
        local_patches_path: Path to the local manifest file

    Returns:
        Dictionary containing patch information
    """
    if local_patches_path.exists():
        logging.info("\tretrieving local manifest")
        file_content = local_patches_path.read_text()
        file_json = json.loads(file_content)
    else:
        logging.info("\tlocal manifest not found, downloading from ESRI")
        esri_response = get_esri_patches()
        local_patches_path.write_bytes(esri_response.content)
        file_json = json.loads(esri_response.text)
    return file_json


def get_esri_patches() -> requests.Response:
    """
    Download the latest patch information from ESRI.

    Makes an HTTP request to the ESRI patches URL and returns the response.
    Raises an exception if the request fails.

    Returns:
        Response object containing the patches JSON data

    Raises:
        requests.HTTPError: If the HTTP request fails
    """
    r = requests.get(url=ESRI_PATCHES_URL)
    r.raise_for_status()
    return r


def main():
    """
    Execute the main patch notification workflow.

    1. Get the local and online patch information
    2. Compare the patches to identify new ones
    3. If no new patches, send a notification that all is current
    4. If new patches found, format details and send notification
    5. Update the local manifest file with the latest data

    Handles exceptions by sending email notifications about failures.
    """
    try:
        local_patches = get_local_patches(local_patches_path=ARCGIS_PATCHES_FILE)
        esri_patches = get_esri_patches()
        patches_online = find_product(
            product_version=ARCGIS_VERSIONS, patch_json=json.loads(esri_patches.text)
        )
        patches_local = find_product(
            product_version=ARCGIS_VERSIONS, patch_json=local_patches
        )

        if patches_online == patches_local:
            logging.info("\tno new patches available")

            send_email(
                msg_to=MESSAGE_RECIPIENTS,
                msg_subject=f"No New ArcGIS Patches Available for Version(s) {ARCGIS_VERSIONS}",
                msg_content="No New ArcGIS Patches Available",
            )
        else:
            new_patches = format_patch_differences(
                patches_local=patches_local, patches_online=patches_online
            )
            logging.info("\tnew patches available, sending email")
            send_email(
                msg_to=MESSAGE_RECIPIENTS,
                msg_subject=f"New ArcGIS Patches Available for Version(s) {ARCGIS_VERSIONS}",
                msg_content=f"New ArcGIS Patches Available:\n\n{new_patches}",
                msg_priority=1,
            )
            logging.info("\toverwriting local manifest")
            ARCGIS_PATCHES_FILE.write_bytes(esri_patches.content)
    except Exception as e:
        send_email(
            msg_subject=f"failure, {current_file.name}",
            msg_content=f"""ArcGIS Patch Notifier Failed with an Unexpected Error\n\nPlease review the logs on {os.environ["COMPUTERNAME"].lower()} at:\n{current_file.stem}.log\n\nError as follows:\n{e}""",
            msg_to=MESSAGE_RECIPIENTS,
            msg_priority=1,
        )


if __name__ == "__main__":
    main()
