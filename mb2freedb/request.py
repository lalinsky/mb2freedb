# Copyright (C) 2011 Lukas Lalinsky
# Distributed under the MIT license, see the LICENSE file for details.

import logging
import mb2freedb

logger = logging.getLogger(__name__)


class CDDB(object):

    EOL = "\r\n"

    def __init__(self, config, conn):
        self.config = config
        self.conn = conn
        self.cmd = None
        self.proto = None

    def handle_cmd_cddb_query(self):
        """Perform a CD search based on either the FreeDB DiscID or the CD TOC."""
        if len(self.cmd) < 3:
            return ["500 Command syntax error."]

        discid = self.cmd[0]
        try:
            int(discid, 16)
        except ValueError:
            return ["500 ID not hex."]

        try:
            num_tracks = int(self.cmd[1])
        except ValueError:
            return ["500 Command syntax error."]

        if len(self.cmd) < 3 + num_tracks:
            return ["500 Command syntax error."]

        offsets = []
        for i in xrange(2, 2 + num_tracks):
            offsets.append(int(self.cmd[i]))
        offsets.append(int(self.cmd[2 + num_tracks]) * 75)

        durations = []
        for i in xrange(num_tracks):
            durations.append((offsets[i + 1] - offsets[i]) * 1000 / 75)

        toc_query = """
            SELECT DISTINCT
                m.id,
                CASE
                    WHEN (SELECT count(*) FROM medium WHERE release = r.id) > 1 THEN
                        rn.name || ' (disc ' || m.position::text || ')'
                    ELSE
                        rn.name
                END AS title,
                CASE
                    WHEN artist_name.name = 'Various Artists' THEN
                        'Various'
                    ELSE
                        artist_name.name
                END AS artist
            FROM
                medium m
                JOIN tracklist t ON t.id = m.tracklist
                JOIN tracklist_index ti ON ti.tracklist = t.id
                JOIN release r ON m.release = r.id
                JOIN release_name rn ON r.name = rn.id
                JOIN artist_credit ON r.artist_credit = artist_credit.id
                JOIN artist_name ON artist_credit.name = artist_name.id
            WHERE
                toc <@ create_bounding_cube(%(durations)s, %(fuzzy)s::int) AND
                track_count = %(num_tracks)s
        """

        discid_query = """
            SELECT DISTINCT
                m.id,
                CASE
                    WHEN (SELECT count(*) FROM medium WHERE release = r.id) > 1 THEN
                        rn.name || ' (disc ' || m.position::text || ')'
                    ELSE
                        rn.name
                END AS title,
                CASE
                    WHEN artist_name.name = 'Various Artists' THEN
                        'Various'
                    ELSE
                        artist_name.name
                END AS artist
            FROM
                medium m
                JOIN medium_cdtoc mc ON m.id = mc.medium
                JOIN cdtoc c ON c.id = mc.cdtoc
                JOIN tracklist t ON t.id = m.tracklist
                JOIN release r ON m.release = r.id
                JOIN release_name rn ON r.name = rn.id
                JOIN artist_credit ON r.artist_credit = artist_credit.id
                JOIN artist_name ON artist_credit.name = artist_name.id
            WHERE
                c.freedb_id = %(discid)s AND
                t.track_count = %(num_tracks)s
        """

        #used_toc = False
        #rows = self.conn.execute(discid_query, dict(discid=discid, num_tracks=num_tracks)).fetchall()
        #if not rows:
        used_toc = True
        rows = self.conn.execute(toc_query, dict(durations=durations, num_tracks=num_tracks, fuzzy=10000)).fetchall()

        if not rows:
            return ["202 No match found."]

        # Only one match and we didn't use the TOC
        if len(rows) == 1 and not used_toc:
            id, title, artist = rows[0]
            return ["200 rock %08x %s / %s" % (id, artist, title)]

        # Found multiple matches
        res = ["211 Found inexact matches, list follows (until terminating `.')"]
        for id, title, artist in rows:
            res.append("rock %08x %s / %s" % (id, artist, title))
        res.append(".")
        return res

    def handle_cmd_cddb_read(self):
        """Read entry from database."""
        if len(self.cmd) < 2:
            return ["500 Command syntax error."]

        if self.cmd[0] != 'rock':
            return ["401 Specified CDDB entry not found."]

        try:
            medium_id = int(self.cmd[1], 16)
        except ValueError:
            return ["500 ID not hex."]

        release_query = """
            SELECT
                CASE
                    WHEN (SELECT count(*) FROM medium WHERE release = r.id) > 1 THEN
                        rn.name || ' (disc ' || m.position::text || ')'
                    ELSE
                        rn.name
                END AS title,
                CASE
                    WHEN racn.name = 'Various Artists' THEN
                        'Various'
                    ELSE
                        racn.name
                END AS artist,
                r.date_year AS year,
                m.tracklist
            FROM medium m
            JOIN release r ON m.release = r.id
            JOIN release_name rn ON r.name = rn.id
            JOIN artist_credit rac ON r.artist_credit = rac.id
            JOIN artist_name racn ON rac.name = racn.id
            WHERE m.id = %(medium_id)s
        """
        rows = self.conn.execute(release_query, dict(medium_id=medium_id)).fetchall()
        if not rows:
            return ["401 Specified CDDB entry not found."]
        release = rows[0]

        tracks_query = """
            SELECT
                t.length,
                tn.name AS title,
                CASE
                    WHEN tacn.name = 'Various Artists' THEN
                        'Various'
                    ELSE
                        tacn.name
                END AS artist
            FROM track t
            JOIN track_name tn ON t.name = tn.id
            JOIN artist_credit tac ON t.artist_credit = tac.id
            JOIN artist_name tacn ON tac.name = tacn.id
            WHERE t.tracklist = %(tracklist_id)s
            ORDER BY t.position
        """
        tracks = self.conn.execute(tracks_query, dict(tracklist_id=release['tracklist'])).fetchall()

        res = ["210 OK, CDDB database entry follows (until terminating `.')"]
        res.append("# xmcd CD database file")
        res.append("#")
        res.append("# Track frame offsets:")
        offset = 150
        disc_length = 0
        artists = set()
        for track in tracks:
            res.append("#\t%d" % (offset,))
            offset += track['length'] * 75 / 1000
            disc_length += track['length'] / 1000
            artists.add(track['artist'])
        res.append("#")
        res.append("# Disc length: %s seconds" % (disc_length,))
        res.append("#")
        res.append("# Revision: 1")
        res.append("# Processed by: mb2freedb %s\r" % (mb2freedb.__version__))
        res.append("# Submitted via: mb2freedb %s MusicBrainz FREEDB gateway\r" % (mb2freedb.__version__))
        res.append("#")
        res.append("DISCID=%08x" % (medium_id,))
        res.append("DTITLE=%s / %s" % (release['artist'], release['title']))
        if self.proto == '5' or self.proto == '6':
            res.append("DYEAR=%s" % (release['year'] or '',))
            res.append("DGENRE=Unknown")
        if len(artists) > 1:
            for i, track in enumerate(tracks):
                res.append("TTITLE%d=%s / %s" % (i, track['artist'], track['title']))
        else:
            for i, track in enumerate(tracks):
                res.append("TTITLE%d=%s" % (i, track['title']))
        res.append("EXTD=")
        for i in xrange(len(tracks)):
            res.append("EXTT%d=" % (i,))
        res.append("PLAYORDER=")
        res.append(".")
        return res

    def handle_cmd_cddb_lscat(self):
        return [
            "210 OK, category list follows (until terminating `.')",
            "rock", "."
        ]

    def handle_cmd_sites(self):
        return [
            "210 OK, site information follows (until terminating `.')",
            "%s http %d /~cddb/cddb.cgi N000.00 W000.00 MusicBrainz FREEDB gateway" % (config.server_name, config.server_port),
            "."
        ]

    def handle_cmd_motd(self):
        return [
            "210 Last modified: 07/04/2006 12:00:00 MOTD follows (until terminating `.')",
            "Welcome to the MusicBrainz FREEDB gateway.",
            "You can find the MusicBrainz website at http://musicbrainz.org/",
            "."
        ]

    def handle_cmd_stat(self):
        return [
            "210 OK, status information follows (until terminating `.')",
            "Server status:",
            "    current proto: 6",
            "    max proto: 6",
            "    interface: http",
            "    gets: no",
            "    puts: no",
            "    updates: no",
            "    posting: no",
            "    validation: accepted",
            "    quotes: yes",
            "    strip ext: no",
            "    secure: no",
            "    current users: 1",
            "    max users: 1",
            "Database entries: 2",
            "Database entries by category:",
            "    rock: 1",
            "    jazz: 1",
            "."
        ]

    def handle_cmd_whom(self):
        return ["401 No user information available."]

    def handle_cmd_ver(self):
        return ["200 mb2freedb %s, Copyright (c) 2006,2011 Lukas Lalinsky." % (__version__,)]

    def handle_cmd_help(self):
        return [
            "210 OK, help information follows (until terminating `.')",
            "The following commands are supported:",
            "",
            "CDDB <subcmd> (valid subcmds: HELLO LSCAT QUERY READ UNLINK WRITE)",
            "DISCID <ntrks> <off_1> <off_2> <...> <off_n> <nsecs>",
            "GET <file>",
            "HELP [command [subcmd]]",
            "LOG [-l lines] [get [-f flag]] [start_time [end_time]] | [day [days]]",
            "MOTD",
            "PROTO [level]",
            "PUT <file>",
            "QUIT",
            "SITES",
            "STAT",
            "UPDATE",
            "VALIDATE",
            "VER",
            "WHOM",
            "."
        ]

    def handle_cmd_cddb(self):
        func_name = 'handle_cmd_cddb_' + self.cmd.pop(0)
        if hasattr(self, func_name):
            return getattr(self, func_name)()
        return ["500 Command syntax error, command unknown, command unimplemented."]

    def handle_cmd(self):
        if not self.cmd or not self.proto:
            return ["500 Command syntax error: incorrect number of arguments."]
        self.cmd = self.cmd.lower().split()
        func_name = 'handle_cmd_' + self.cmd.pop(0)
        if hasattr(self, func_name):
            return getattr(self, func_name)()
        return ["500 Command syntax error, command unknown, command unimplemented."]

    def handle(self, args):
        self.cmd = args.get("cmd", [None])[0]
        self.proto = args.get("proto", [None])[0]
        response = self.EOL.join(self.handle_cmd()).encode('utf8') + self.EOL
        logger.debug("Request %s:\n%s\n", args, response)
        return response


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    httpd = make_server('localhost', 8051, application)
    httpd.serve_forever()

