#!/usr/bin/env python3
"""
Helper for managing extensions across agents.

Usage:
  python3 src/ext.py add-shared <settings.json> <relpath>
  python3 src/ext.py remove-shared <settings.json> <relpath>
  python3 src/ext.py list-pkgs <settings.json>
  python3 src/ext.py list-extensions <settings.json>
  python3 src/ext.py has-ext <settings.json> <relpath>
"""

import json, sys

def read_settings(path):
    with open(path) as f:
        return json.load(f)

def write_settings(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

def add_shared(path, relpath):
    d = read_settings(path)
    exts = d.setdefault('extensions', [])
    if relpath not in exts:
        exts.append(relpath)
        write_settings(path, d)
        return True
    return False

def remove_shared(path, relpath):
    d = read_settings(path)
    exts = d.get('extensions', [])
    if relpath in exts:
        exts.remove(relpath)
        d['extensions'] = exts
        write_settings(path, d)
        return True
    return False

def list_pkgs(path):
    d = read_settings(path)
    return d.get('packages', [])

def list_extensions(path):
    d = read_settings(path)
    return d.get('extensions', [])

def has_ext(path, relpath):
    d = read_settings(path)
    return relpath in d.get('extensions', [])

if __name__ == '__main__':
    cmd = sys.argv[1]
    path = sys.argv[2]

    if cmd == 'add-shared':
        relpath = sys.argv[3]
        changed = add_shared(path, relpath)
        print('added' if changed else 'exists')

    elif cmd == 'remove-shared':
        relpath = sys.argv[3]
        changed = remove_shared(path, relpath)
        print('removed' if changed else 'not-found')

    elif cmd == 'list-pkgs':
        for p in list_pkgs(path):
            print(p)

    elif cmd == 'list-extensions':
        for e in list_extensions(path):
            print(e)

    elif cmd == 'has-ext':
        relpath = sys.argv[3]
        print('yes' if has_ext(path, relpath) else 'no')
