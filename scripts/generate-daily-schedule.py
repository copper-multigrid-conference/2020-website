"""Generate a daily schedule
"""
import re
import subprocess

import bs4 as bs
import requests


def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    regex = re.compile('|'.join(re.escape(str(key)) for key in sorted(conv.keys(), key=lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)


latexdoc2 = r'''\documentclass{article}
\usepackage[landscape,vmargin=0.5in,hmargin=0.5in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage[defaultfam,light,tabular,lining]{montserrat}
\usepackage[table]{xcolor}

% basic column sizes
\newlength\qs
\setlength\qs{\dimexpr .08\textwidth -2\tabcolsep}
\newlength\ql
\setlength\ql{\dimexpr .34\textwidth -2\tabcolsep}

% multicolumns
\newlength\qsessfull
\setlength\qsessfull{\dimexpr .92\textwidth -2\tabcolsep}
\newlength\qsesspart
\setlength\qsesspart{\dimexpr .42\textwidth -2\tabcolsep}
\newlength\qtitlefull
\setlength\qtitlefull{\dimexpr .84\textwidth -2\tabcolsep}

\newcommand{\sessfull}[1]{\multicolumn{5}{p{\qsessfull}}{#1}}
\newcommand{\sesspart}[1]{\multicolumn{2}{p{\qsesspart}}{#1}}
\newcommand{\titlefull}[1]{\multicolumn{4}{p{\qtitlefull}}{#1}}

\begin{document}
'''

latexdoc3 = r'''\documentclass[9pt]{article}
\usepackage[landscape,vmargin=0.5in,hmargin=0.5in]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage[defaultfam,light,tabular,lining]{montserrat}
\usepackage[table]{xcolor}

% basic column sizes
\newlength\qs
\setlength\qs{\dimexpr .05\textwidth -2\tabcolsep}
\newlength\ql
\setlength\ql{\dimexpr .23\textwidth -2\tabcolsep}

% multicolumns
\newlength\qsessfull
\setlength\qsessfull{\dimexpr .95\textwidth -2\tabcolsep}
\newlength\qtitlefull
\setlength\qtitlefull{\dimexpr .90\textwidth -2\tabcolsep}
\newlength\qsesspart
\setlength\qsesspart{\dimexpr .28\textwidth -2\tabcolsep}

\newcommand{\sessfull}[1]{\multicolumn{8}{p{\qsessfull}}{#1}}
\newcommand{\titlefull}[1]{\multicolumn{7}{p{\qtitlefull}}{#1}}
\newcommand{\sesspart}[1]{\multicolumn{2}{p{\qsesspart}}{#1}}

\begin{document}
'''

latexdoc0 = latexdoc3

latexdoc1 = r'''\end{document}
'''


def scrub_data(soup):
    """
    scrub data
    """
    raw = False
    sessiondata = []

    sessions = soup.findAll("div", {"class": "session"})
    for session in sessions:
        session_time = session.findAll('span', {"class": "interval"})[0].text

        session_name = session.findAll('span', {"class": "title"})[0].text
        part = 'full'
        m = re.match("Session\s+[0-9]+([A,B,C]):", session_name)
        if m:
            part = m.groups(0)[0]

        if raw:
            print("{}: {}".format(session_time, session_name))
        talks = session.findAll('table')

        talkdata = []
        if talks:
            for talk in talks[0].findAll('tr'):
                talk_time = talk.findAll('td', {"class": "time"})[0].text
                authors = talk.findAll('div', {"class": "authors"})[0]
                talk_authors = [t.text for t in authors.findAll('a', {"class": "person"})]
                speakers = talk.findAll('div', {"class": "speaker"})
                if speakers:
                    talk_speaker = speakers[0].findAll('a', {"class": "person"})[0].text
                else:
                    talk_speaker = talk_authors[0]
                talk_title = talk.findAll('div', {"class": "title"})[0].text
                if raw:
                    auths = [f'**{a}**' if a == talk_speaker else a for a in talk_authors]
                    print('          {}: {}'.format(talk_time, ', '.join(auths)))
                    print('                 {}'.format(talk_title))
                talkdata.append([talk_time, talk_authors, talk_speaker, talk_title])

        sessiondata.append([session_time, session_name, part, talkdata])
    return sessiondata


def fsess(mystr):
    """session formatting"""
    mystr = tex_escape(mystr)
    return f'\\textbf{{{mystr}}}'


def ftitle(mystr):
    """title formatting"""
    return f'\\textit{{{mystr}}}'


def fspeaker(mystr):
    """speaker formatting"""
    return f'{{\\color{{black!70}}\\fontseries{{mb}}\\selectfont {mystr}}}'


def froom(mystr):
    """room formatting"""
    return f'{{\\color{{black!70}}\\fontseries{{mb}}\\selectfont {mystr}}}'


def fauth(mystr):
    """author formatting"""
    return f'{{\\tiny \\color{{black!70}}\\selectfont {mystr}}}'


def fstime(mystr):
    """time formatting"""
    return f'\\textbf{{{mystr}}}'


def generate_tex(sessiondata, rooms, np=3):
    """
    np = number of parallel sessions

    This sets up a grid with np frames:

    |     0      |       1    |      2     |
    |--|---------|--|---------|--|---------|
    |--|--|------|--|--|------|--|--|------|

    or

    |           0      |              1    |
    |----|-------------|----|--------------|
    |----|----|--------|----|----|---------|

    |8-10| Session 6                       |
    |8-9 | Some talk title                 |
    |9-10| Some talk title                 |
    |8-10| Session 6A  |8-10|Session 6B    |
    |8-9 | Some talk   |8-9 |Some talk     |
         | title       |    |title         |
    |9-10| Some talk   |9-10|Some talk     |
         | title       |    |title         |

    The sizes are
    | qs | qs  |   ql  | qs | qs  |   ql   |
    """
    pstr = r'p{\qs}p{\qs}p{\ql}' * np
    latexmain = r'\noindent\begin{longtable}{' + pstr + '}\n'
    midrule0 = '\\arrayrulecolor{black!20}\\midrule'

    s = 0
    while s < len(sessiondata):
        # fill these with 1, 2, ..., np == # of parallel sessions
        session_time = []
        session_name = []
        part = []
        talkdata = []
        room = []

        thispart = sessiondata[s][2]
        if thispart == 'full':
            np = 1
        elif thispart == 'A':
            # figure out how many parallel sessions
            parallel = True
            np = 1
            while parallel:
                if s + np < len(sessiondata):
                    if sessiondata[s + np][2] != 'full' and sessiondata[s + np - 1][2] < sessiondata[s + np][2]:
                        np += 1
                    else:
                        parallel = False
                else:
                    parallel = False
        else:
            s += 1
            continue

        # load all np parallel sessions
        for t in range(s, s + np):
            session_timeX, session_nameX, partX, talkdataX = sessiondata[t]
            session_timeX = fstime(session_timeX)
            session_nameX = fsess(tex_escape(session_nameX))
            if any(s in session_nameX for s in ['Breakfast', 'Coffee', 'Lunch', 'Banquet']):
                roomX = ''
            else:
                roomX = froom(rooms[partX])

            session_time.append(session_timeX)
            session_name.append(session_nameX)
            part.append(partX)
            talkdata.append(talkdataX)
            room.append(roomX)

        # write the session header
        if np == 1:
            latexmain += f'{session_time[-1]} & \\sessfull{{{session_name[-1]} \\quad {room[-1]}}} \\\\{midrule0}\n'
        if np > 1:
            for t in range(np):
                latexmain += f'{session_time[t]} & \\sesspart{{{session_name[t]} \\quad {room[t]}}} '
                if t < np-1:
                    latexmain += '& '
                else:
                    latexmain += f'\\\\{midrule0}\n'

        # write each talk
        if len(talkdata[0]):

            # get all of the talk times
            alltimes = []
            for i in range(np):
                alltimes += [t[0] for t in talkdata[i]]
                alltimes = list(set(alltimes))
                alltimes.sort()

            # for each talk time:
            # 1. find the talk
            # 2. list the time, speaker, authors, title in each session
            for time in alltimes:
                time_speaker = []
                time_authors = []
                time_titles = []
                for i in range(np):
                    talkfound = False
                    for j in range(len(talkdata[i])):
                        if talkdata[i][j][0] == time:
                            talkfound = True
                            talk_authors = talkdata[i][j][1]
                            talk_speaker = talkdata[i][j][2]

                            other_authors = ', '.join([a for a in talk_authors if a != talk_speaker])
                            other_authors = fauth(other_authors)
                            talk_speaker = fspeaker(talk_speaker)

                            time_speaker.append(talk_speaker)
                            time_authors.append(other_authors)
                            time_titles.append(talkdata[i][j][3])
                    if not talkfound:
                            time_speaker.append('')
                            time_authors.append('')
                            time_titles.append('---')

                midrule = ''
                if time == alltimes[-1]:
                    midrule = midrule0

                if np == 1:
                    latexmain += f'& {time} & \\titlefull{{{time_titles[0]}\\newline {time_speaker[0]} {time_authors[0]}}} \\\\{midrule}\n'
                else:
                    for i in range(np):
                        latexmain += f'& {time} & {time_titles[i]}\\newline {time_speaker[i]} {time_authors[i]} '
                        if i < np-1:
                            latexmain += ' & '
                        if i == np-1:
                            latexmain += f' \\\\{midrule}\n'

            latexmain += '\\pagebreak\n'
        s += 1

    latexmain += r'\end{longtable}'
    return latexmain


# full, parallel A, B, C
rooms = {'full': 'Bighorn B',
         'A': 'Bighorn B',
         'B': 'Bighorn C/1',
         'C': 'Bighorn C/2'}

data = {'Saturday 3/21': 'https://easychair.org/smart-program/CM2020/2020-03-21.html',
        'Sunday 3/22': 'https://easychair.org/smart-program/CM2020/2020-03-22.html',
        'Monday 3/23': 'https://easychair.org/smart-program/CM2020/2020-03-23.html',
        'Tuesday 3/24': 'https://easychair.org/smart-program/CM2020/2020-03-24.html',
        'Wednesday 3/25': 'https://easychair.org/smart-program/CM2020/2020-03-25.html',
        'Thursday 3/26': 'https://easychair.org/smart-program/CM2020/2020-03-26.html'
        }

for d in data:
    print(f'Retreiving {d}')
    url = requests.get(data[d]).text
    #import pickle
    #with open('url.pk', 'wb') as f:
    #    pickle.dump(url, f)
    #with open('url.pk', 'rb') as f:
    #    url = pickle.load(f)
    soup = bs.BeautifulSoup(url, 'lxml')

    print(f'-Scrubbing {d}')
    sessiondata = scrub_data(soup)

    print(f'-Generating {d}')
    latexmain = generate_tex(sessiondata, rooms)

    title = f'{{\\centering\\LARGE\\textbf{{ {d} }}}}\\bigskip\\bigskip\n\n'
    filename = d.replace(' ', '-').replace('/', '-') + '.tex'
    with open(filename, "w") as texfile:
        print(latexdoc0 + title + latexmain + latexdoc1, file=texfile)

    print(f'-Building {filename}')
    subprocess.check_call(['latexrun', filename])
