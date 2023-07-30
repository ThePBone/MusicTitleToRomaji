import argparse
import os
import unicodedata

import mutagen.flac
import wcwidth

import music_tag
import pykakasi
from music_tag.file import TAG_MAP_ENTRY
from mutagen import MutagenError

cjk_ranges = [
    {"from": ord(u"\u3300"), "to": ord(u"\u33ff")},  # compatibility ideographs
    {"from": ord(u"\ufe30"), "to": ord(u"\ufe4f")},  # compatibility ideographs
    {"from": ord(u"\uf900"), "to": ord(u"\ufaff")},  # compatibility ideographs
    {"from": ord(u"\U0002F800"), "to": ord(u"\U0002fa1f")},  # compatibility ideographs
    {'from': ord(u'\u3040'), 'to': ord(u'\u309f')},  # Japanese Hiragana
    {"from": ord(u"\u30a0"), "to": ord(u"\u30ff")},  # Japanese Katakana
    {"from": ord(u"\u2e80"), "to": ord(u"\u2eff")},  # cjk radicals supplement
    {"from": ord(u"\u4e00"), "to": ord(u"\u9fff")},
    {"from": ord(u"\u3400"), "to": ord(u"\u4dbf")},
    {"from": ord(u"\U00020000"), "to": ord(u"\U0002a6df")},
    {"from": ord(u"\U0002a700"), "to": ord(u"\U0002b73f")},
    {"from": ord(u"\U0002b740"), "to": ord(u"\U0002b81f")},
    {"from": ord(u"\U0002b820"), "to": ord(u"\U0002ceaf")}  # included as of Unicode 8.0
]


def is_char_cjk(char):
    return any([unicode_range["from"] <= ord(char) <= unicode_range["to"] for unicode_range in cjk_ranges])


def is_cjk(string):
    return any(is_char_cjk(c) for c in string)


def pad(text, width):
    text_width = 0
    for ch in text:
        text_width += wcwidth.wcwidth(ch)
    if width <= text_width:
        return text
    return text + ' ' * (width - text_width)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dry-run", help="Perform dry run", action='store_true')
    parser.add_argument("-a", "--append-original", help="Append original title (in brackets)", action='store_true')
    parser.add_argument("-r", "--restore", help="Restore original title", action='store_true')
    parser.add_argument('directory')
    args = parser.parse_args()

    kks = pykakasi.Kakasi()

    no_cjk = 0
    skipped = 0
    processed = 0

    for root, dirs, files in os.walk(args.directory):
        for file in files:
            if not file.endswith(('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.')):
                continue

            try:
                music = music_tag.load_file(os.path.join(root, file))
            except MutagenError as e:
                print(e)
                print(f"--> Failed to handle file: '{os.path.join(root, file)}'")
                print("File may be corrupt or empty. Please check.")
                exit(1)

            music.tag_map['originaltitle'] = TAG_MAP_ENTRY(type=str)
            old_title = music['title'].value

            if args.restore:
                tup = [item for item in music.mfile.tags if item[0].lower() == "originaltitle"]
                if len(tup) > 0:
                    if not args.dry_run:
                        music['title'] = tup[0][1]
                        music.mfile.tags.remove(tup[0])
                        music.save()
                    processed += 1
                else:
                    skipped += 1
                continue

            if not is_cjk(old_title):
                no_cjk += 1
                continue

            if 'originaltitle' in music.raw.parent.mfile.tags:
                skipped += 1
                continue

            new_title = ''
            for segment in kks.convert(old_title):
                new_segment = segment['hepburn']
                # Capitalize, if segment was converted
                if segment['orig'] != segment['hepburn']:
                    new_segment = new_segment.capitalize()
                new_title += new_segment + ' '

            # Remove duplicate whitespaces
            new_title = ' '.join(new_title.split())
            # Remove other unneeded whitespaces
            new_title = new_title \
                .replace(" .", ".") \
                .replace(" !", "!") \
                .replace("“ ", "“") \
                .replace(" ”", "”") \
                .replace(" ,", ",") \
                .replace(" :", ":") \
                .replace("( ", "(") \
                .replace(" )", ")")

            # We don't need that twice...
            if args.append_original:
                new_title = new_title.replace("(Instrumental)", "")

            new_title = new_title.strip()

            # Append old title
            if args.append_original:
                new_title += " [" + old_title + "]"

            if len(new_title) < 1:
                new_title = old_title

            if not args.dry_run:
                music['title'] = new_title
                if 'originaltitle' not in [x[0].lower() for x in music.mfile.tags]:
                    music.mfile.tags.append(('originaltitle', old_title))
                music.save()

            processed += 1
            print(f'{pad(old_title, 50)} {new_title:40s}')

    if args.restore:
        print("{:<6}items restored.\n{:<6}items had no original title.".format(processed, skipped))
    else:
        print("{:<6}new items processed.\n{:<6}items already converted.\n{:<6}items had no CJK characters."
              .format(processed, skipped, no_cjk))


if __name__ == '__main__':
    main()
