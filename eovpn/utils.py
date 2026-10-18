import os
import logging
import zipfile
import io
import shutil
import re
import shlex
import subprocess
import gettext
import urllib.request
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk

logger = logging.getLogger(__name__)


class NotZipException(Exception):
    pass

def download_remote_to_destination(remote, destination):

    ovpn = re.compile('.ovpn')
    crt = re.compile(r'.crt|cert|pem')
     
    def make_zip_from_b(content):
        return zipfile.ZipFile(io.BytesIO(content), "r")

    def download_zip(remote):
        if os.path.exists(remote):
            f = open(remote, "rb")
            return make_zip_from_b(f.read())
        else:
            hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'}
            req = urllib.request.Request(remote, headers=hdr)
            remote_c = urllib.request.urlopen(req)  
            return make_zip_from_b(remote_c.read())

    remote = os.path.expanduser(remote)

    try:
        zip_file = download_zip(remote)
    except:
        raise NotZipException(gettext.gettext("Configuration Source MUST be a ZIP file."))    
        
    #list of files inside zip
    files_in_zip = zip_file.namelist()

    configs = list( filter(ovpn.findall, files_in_zip) )
    certs = list( filter(crt.findall, files_in_zip) )
    all_files = configs + certs
    if len(configs) > 0:
        for file_name in all_files:      
            file = zip_file.getinfo(file_name)
            file.filename = os.path.basename(file.filename) #remove nested dir
            logger.info(file.filename)
            zip_file.extract(file, destination)
    
    return certs

def resolve_file(filepath: str, search_dirs: list = None) -> str | None:
    """Resolve a relative or absolute file path against search directories."""
    if not filepath:
        return None
    filepath = filepath.replace("\\", "/")
    expanded = os.path.expanduser(filepath)
    if os.path.isabs(expanded) and os.path.exists(expanded):
        return expanded
    if search_dirs:
        for d in search_dirs:
            if not d:
                continue
            candidate = os.path.join(os.path.expanduser(d), filepath)
            if os.path.exists(candidate):
                return candidate
            candidate_base = os.path.join(os.path.expanduser(d), os.path.basename(filepath))
            if os.path.exists(candidate_base):
                return candidate_base
    return None

def inline_ovpn_config_content(content: str, search_dirs: list = None, ca_override: str = None) -> str:
    """
    Inline external files (ca, cert, key, tls-auth, etc.) into XML-style tags
    so that backends like OpenVPN 3 and NetworkManager can parse them without
    needing file access to external/relative certificates and keys.
    """
    if search_dirs is None:
        search_dirs = []

    ca_content = None
    if ca_override and os.path.exists(ca_override):
        try:
            ca_content = Path(ca_override).read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            logger.error("Failed to read ca_override %s: %s", ca_override, e)

    existing_tags = set(re.findall(r'<([a-zA-Z0-9_\-]+)>', content))
    if ca_content and "ca" in existing_tags:
        content = re.sub(r'<ca>.*?</ca>', f'<ca>\n{ca_content}\n</ca>', content, flags=re.DOTALL | re.IGNORECASE)

    has_key_direction = bool(re.search(r'^\s*key-direction\s+', content, re.MULTILINE))
    lines = content.splitlines()
    output_lines = []
    inlined_tags = {}
    key_direction_to_add = None

    if ca_content and "ca" not in existing_tags:
        inlined_tags["ca"] = ca_content

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            output_lines.append(line)
            continue

        try:
            parts = shlex.split(line, comments=True)
        except Exception:
            parts = stripped.split()

        if not parts:
            output_lines.append(line)
            continue

        directive = parts[0].lower()

        if directive == "auth-user-pass" and len(parts) > 1:
            output_lines.append("auth-user-pass")
            continue

        if directive == "ca":
            if ca_content:
                output_lines.append(f"# inlined: {line}")
                continue
            elif "ca" not in existing_tags and len(parts) > 1:
                resolved = resolve_file(parts[1], search_dirs)
                if resolved:
                    inlined_tags["ca"] = Path(resolved).read_text(encoding="utf-8", errors="replace").strip()
                    output_lines.append(f"# inlined: {line}")
                    continue

        if directive == "tls-auth" and len(parts) > 1:
            if "tls-auth" not in existing_tags:
                resolved = resolve_file(parts[1], search_dirs)
                if resolved:
                    inlined_tags["tls-auth"] = Path(resolved).read_text(encoding="utf-8", errors="replace").strip()
                    if len(parts) > 2 and parts[2] in ("0", "1") and not has_key_direction:
                        key_direction_to_add = parts[2]
                        has_key_direction = True
                    output_lines.append(f"# inlined: {line}")
                    continue

        if directive in ("cert", "key", "tls-crypt", "tls-crypt-v2", "extra-certs", "crl-verify") and len(parts) > 1:
            tag = directive
            if tag not in existing_tags:
                resolved = resolve_file(parts[1], search_dirs)
                if resolved:
                    inlined_tags[tag] = Path(resolved).read_text(encoding="utf-8", errors="replace").strip()
                    output_lines.append(f"# inlined: {line}")
                    continue

        output_lines.append(line)

    if key_direction_to_add is not None:
        output_lines.append(f"key-direction {key_direction_to_add}")

    for tag, t_content in inlined_tags.items():
        output_lines.append(f"<{tag}>\n{t_content}\n</{tag}>")

    return "\n".join(output_lines) + "\n"

def ovpn_is_auth_required(ovpn_file):
    try:
        with open(ovpn_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(("#", ";")):
                    continue
                if stripped.startswith("auth-user-pass"):
                    return True
    except Exception:
        pass
    return False