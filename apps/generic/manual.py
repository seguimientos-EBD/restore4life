"""The screenshots of the two manuals, and what each numbered mark on them points at.

The prose lives in the templates; this file holds only what the templates cannot say
tidily -- where every mark sits on top of its screenshot -- because that is the part
that gets adjusted most and is unreadable spread through the markup.

A mark is placed in percentages of the image, not pixels, so a screenshot retaken at a
different window size keeps its marks roughly in place. To find the numbers, open any
manual page with `?markers=1` and click on the screenshot: the position under the
pointer is written next to it, ready to be pasted here.

Screenshots go in `static/img/manual/` under the name and extension each figure
declares. Missing ones are not an error: the page draws a placeholder naming the file
it expects and listing the marks it is waiting for, so an incomplete manual reads as a
checklist of what is left to capture rather than as a page of broken images.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mark:
    """A numbered circle on a screenshot, and the line that explains it.

    `x` and `y` are percentages of the image, measured from its top-left corner, and
    are the centre of the circle.
    """

    x: float
    y: float
    text: str


@dataclass(frozen=True)
class Figure:
    """A screenshot with its caption and its marks.

    `name` is the file inside `static/img/manual/`, without the extension: the
    placeholder needs to name the missing file, so the figure has to know it even when
    it is not there.
    """

    name: str
    alt: str
    caption: str = ''
    marks: list[Mark] = field(default_factory=list)
    # Screenshots of a whole browser window need the page width; a cropped panel or a
    # dialog looks silly stretched across it and is easier to read narrow.
    width: str = 'full'
    # PNG for anything that is mostly interface, where the text has to stay crisp and
    # the flat colours compress to nothing anyway. JPEG for the shots with satellite
    # imagery in them: the same picture is a fifth of the size and no worse to read,
    # which matters because these pages are also printed into committed PDFs.
    ext: str = 'png'

    @property
    def path(self):
        return f'img/manual/{self.name}.{self.ext}'


# --------------------------------------------------------------------------- #
# Manual 1 -- the Earth Engine account                                         #
# --------------------------------------------------------------------------- #

EARTH_ENGINE = {
    'cloud-onboarding': Figure(
        name='cloud-onboarding',
        alt='The Earth Engine page of the Google Cloud console, before any project exists',
        caption='The Earth Engine page of the Cloud console, on a project that has not been '
                'registered yet. This is what it offers until you register: the whole of the '
                'page is an invitation to do so.',
        marks=[
            Mark(29, 4.5, 'The project this page is about. Check it before anything else — '
                          'the console opens on whichever project you used last, which is not '
                          'always the one you mean.'),
            Mark(57, 92.4, 'Starts the questionnaire that decides whether the project is '
                           'commercial or noncommercial.'),
        ],
    ),
    'register-start': Figure(
        name='register-start',
        alt='The registration form of the Earth Engine console, showing its five steps with '
            'the first one open',
        caption='Registration is a form of five steps, opened one at a time. The banner at '
                'the top only appears on a project that is already registered, as this one '
                'is; on a first pass there is nothing there.',
        marks=[
            Mark(30, 43.5, 'The kind of organisation. For the EBD-CSIC and the university '
                           'partners this is an academic institution.'),
            Mark(46, 51.8, 'Opens the next step. Each one unfolds as the one before it is '
                           'answered.'),
            Mark(25, 62, 'The steps still to come. Nothing is submitted until the button at '
                         'the foot of them all.'),
        ],
    ),
    'register-noncommercial': Figure(
        name='register-noncommercial',
        alt='The eligibility step of the registration form, filled in for noncommercial '
            'academic research',
        caption='The step that decides the answer. Everything the consortium does with this '
                'application falls on the noncommercial side, and the box at the foot says so '
                'once the answers add up to it.',
        marks=[
            Mark(30, 25.4, 'The institution. For the consortium this is whichever partner '
                           'employs you.'),
            Mark(30, 37.5, 'Whether anyone pays you for what you make with Earth Engine. '
                           'Research grants are not payment for this purpose.'),
            Mark(30, 42.4, 'Scientific research rather than decision support, which is the '
                           'honest description of hydroperiod work.'),
            Mark(30, 75.7, 'The verdict. Until this box says you are eligible, the '
                           'noncommercial path is not open.'),
        ],
    ),
    'register-summary': Figure(
        name='register-summary',
        alt='The last step of the registration form, listing every answer given before it is '
            'submitted',
        caption='The last step repeats every answer before anything is sent.',
        marks=[
            Mark(25, 27, 'Everything you declared, in one place.'),
            Mark(24, 96.7, 'Submits it. Eligibility is checked against what is declared here, '
                           'so it is worth reading rather than clicking through.'),
        ],
    ),
    'project-id': Figure(
        name='project-id',
        alt='The Cloud console project selector, showing the project ID next to its name',
        caption='The project ID is not the project name. The application asks for the ID: '
                'lowercase, hyphenated, often with digits appended by Google. The project '
                'selector at the top of any Cloud page lists both, side by side.',
        marks=[
            Mark(38, 33.8, 'The display name, which you chose and which the application does '
                           'not want.'),
            Mark(76, 33.8, 'The ID. This is what goes into the connection form.'),
        ],
    ),
    'enable-api': Figure(
        name='enable-api',
        alt='The Earth Engine API page in the Cloud console API library, with the Enable button',
        caption='The Earth Engine API on the project. The registration page usually turns it '
                'on for you; this is where to check when the connection later refuses. Shown '
                'here on a project where it is still off.',
        marks=[
            Mark(38, 6.1, 'The project the button applies to. Check it before clicking: the '
                          'console remembers whichever project you last used, which is not '
                          'always this one.'),
            Mark(30, 69.9, 'Enables the API. Once on, it reads "Manage" instead, and there is '
                           'nothing to do.'),
        ],
    ),
    'tier': Figure(
        name='tier',
        alt='The Earth Engine page for changing the project tier, with Community and '
            'Contributor side by side',
        caption='The tier decides how much computation the project gets each month. New '
                'noncommercial projects land on Community, and this is the page that moves '
                'them off it.',
        marks=[
            Mark(24, 38.5, 'Community, where a new project starts: 150 EECU-hours a month and '
                           'no billing account anywhere in sight.'),
            Mark(24, 46.8, 'Contributor, 1,000 EECU-hours a month. Still free for '
                           'noncommercial use, but it wants a billing account attached to the '
                           'project before it will let you have it.'),
            Mark(40, 93.4, 'Applies the change. Nothing is charged for the noncommercial use '
                           'of either tier.'),
        ],
    ),
    'sign-in': Figure(
        name='sign-in',
        alt='The sign-in screen of the application, asking for an email address',
        caption='The application has no passwords. You give an email address and it sends a '
                'link that signs you in.',
        marks=[
            Mark(50, 64, 'Any address you can read. It becomes your account the first time '
                           'you use it.'),
            Mark(60.5, 72.5, 'Sends the link. It is good for thirty minutes and for one use.'),
        ],
    ),
    'sign-in-sent': Figure(
        name='sign-in-sent',
        alt='The screen confirming that a sign-in link has been sent to the address given',
        caption='The application says where it sent the link. Nothing else happens on this '
                'screen: the next step is in your inbox.',
        marks=[
            Mark(8, 73, 'The address the link went to. Read it: a typo here looks exactly '
                        'like a mail that never arrives.'),
            Mark(55, 88.2, 'Back to the previous screen, to fix the address or ask for '
                           'another link.'),
        ],
    ),
    'sign-in-email': Figure(
        name='sign-in-email',
        alt='The sign-in mail, with the link blotted out',
        caption='The mail itself. The link is one long address with a token on the end of it; '
                'the token is blotted out here because it is the whole of the credential.',
        marks=[
            Mark(36, 8, 'Who it comes from. If it is not in the inbox, it is worth searching '
                        'the spam folder for this address.'),
            Mark(72, 53.4, 'Thirty minutes, and one use. Asking for another costs nothing.'),
            Mark(96, 74.7, 'Following it signs you in and lands you on the home page.'),
        ],
    ),
    'connect-form': Figure(
        name='connect-form',
        alt='The Earth Engine connection screen, asking for a Google Cloud project ID',
        caption='The connection screen, reached from the warning on the home page or from the '
                'Earth Engine badge in the bar at the top.',
        marks=[
            Mark(30, 71.3, 'The project ID from step 2 — the ID, not the display name.'),
            Mark(60, 86, 'Opens the Google authorisation step.'),
        ],
    ),
    'generate-token': Figure(
        name='generate-token',
        alt='The Earth Engine notebook authenticator, naming the account and the project '
            'before it generates a token',
        caption='The link opens here first. It is Earth Engine\'s own page, and its warnings '
                'are aimed at people who arrived from a notebook they did not write; you '
                'arrived from a link this application printed, and the project below is the '
                'one you just typed into it.',
        marks=[
            Mark(23, 25.4, 'The Google account. This is the one being authorised, so it has '
                           'to be the one that owns the project.'),
            Mark(23, 35.9, 'The project. It should read back the ID you gave the '
                           'application.'),
            Mark(62, 95.2, 'Goes on to Google\'s own sign-in and consent screens.'),
        ],
    ),
    'authorize': Figure(
        name='authorize',
        alt='The Google authorisation page, ending with the code to copy back into the '
            'application',
        caption='Google\'s own authorisation page. It ends by showing a long code, which is '
                'what the application is waiting for. The code is blotted out here: it is a '
                'credential, short-lived but real, and this page is printed into a PDF.',
        marks=[
            Mark(48, 44, 'The Google account being authorised. Make sure it is the one that '
                         'owns the project.'),
            Mark(47, 96.4, 'The authorisation code. Copy the whole of it.'),
            Mark(95, 96.4, 'Or copy it from here, which is harder to get wrong than a '
                           'selection.'),
        ],
    ),
    'paste-code': Figure(
        name='paste-code',
        alt='The application waiting for the authorisation code to be pasted',
        caption='Back in the application, the pasted code is exchanged for a token that is '
                'stored encrypted against your account.',
        marks=[
            Mark(6, 50, 'The link to Google, and the warning that it wants a Chromium-based '
                        'browser. It stays here, so a tab closed too early costs nothing.'),
            Mark(30, 80.4, 'Where the code goes.'),
            Mark(58, 88.1, 'Completes the connection.'),
        ],
    ),
    'connected': Figure(
        name='connected',
        alt='The top bar of the application showing the green Earth Engine badge with the project name',
        caption='Connected. The badge names the project every computation will run on, and '
                'clicking it leads back to the screen that can disconnect it.',
        marks=[
            Mark(67, 72, 'The connected project. If this is missing, nothing will compute.'),
        ],
    ),
}


# --------------------------------------------------------------------------- #
# Manual 2 -- the application                                                  #
# --------------------------------------------------------------------------- #

APPLICATION = {
    'home': Figure(
        name='home',
        alt='The home page of the application, listing the study areas as cards',
        caption='The home page. Each card is a study area — a group of wetlands with the '
                'outline the map opens on.',
        marks=[
            Mark(50, 38, 'The outline of every wetland in the study area, drawn small.'),
            Mark(38, 68.4, 'How many areas it holds, Ramsar wetlands and eLTER sites '
                           'together.'),
            Mark(47, 78, 'Opens the workspace, which is where the whole of the rest of this '
                         'manual happens.'),
        ],
    ),
    'workspace': Figure(
        name='workspace',
        alt='The workspace: the control panel on the left and the map on the right',
        caption='The workspace. The panel on the left says what to compute; the map on the '
                'right shows it. Below a wide screen the two stack, panel first.',
        ext='jpg',
        marks=[
            Mark(8.5, 13.6, 'Which area to work on. Picking a source adds a second dropdown '
                            'under this one.'),
            Mark(8.5, 24, 'The time series: the same sensor, period, index and threshold feed '
                          'every tab that needs them.'),
            Mark(12, 36.3, 'The five tabs, one per product.'),
            Mark(20, 70, 'The log, which narrates every request and is where errors show up.'),
            Mark(60, 45, 'The map. Wetlands in blue-grey, eLTER sites in dashed purple, the '
                         'study area outline in gold.'),
            Mark(92.5, 16, 'The layer switcher: basemaps, and every layer you add.'),
            Mark(33.5, 21, 'Drawing tools, and below them the value reader.'),
        ],
    ),
    'area-source': Figure(
        name='area-source',
        alt='The area picker: the source, and under it the area itself',
        caption='The area is chosen in two steps because the three sources together are far '
                'too many entries for one dropdown.',
        marks=[
            Mark(28, 34.5, 'Where the area comes from: the basin\'s Ramsar wetlands, the eLTER '
                           'sites that fall inside it, or a shape of your own.'),
            Mark(28, 74.5, 'Then which one. Picking here also frames the map on it.'),
        ],
    ),
    'draw': Figure(
        name='draw',
        alt='A polygon drawn over the map with the drawing tools, covering part of the '
            'Danube delta',
        caption='A drawn shape overrides whatever the dropdown holds: it is the more '
                'deliberate act of the two, so the application prefers it.',
        ext='jpg',
        marks=[
            Mark(4, 7.8, 'Polygon and rectangle. Either one produces the area to analyse.'),
            Mark(4, 15.2, 'Edit and delete what has been drawn. Deleting it hands the choice '
                          'back to the dropdown.'),
            Mark(46.7, 49, 'The shape itself, in amber over whatever the map already shows.'),
        ],
    ),
    'time-series': Figure(
        name='time-series',
        alt='The time series block of the panel',
        caption='These six fields define the series every product is built from. Changing the '
                'sensor rewrites what the other fields will accept.',
        marks=[
            Mark(28, 11.9, 'Sentinel-2 for detail, Landsat for depth of record, MODIS for very '
                           'large areas.'),
            Mark(28, 32, 'The period, in hydrological years. A cycle labelled 2021 runs from '
                         '1 September 2021 to 1 September 2022.'),
            Mark(28, 52, 'The water index. MNDWI is the sensible default and works on all '
                         'three sensors.'),
            Mark(28, 65.5, 'Above this value a pixel counts as water.'),
            Mark(28, 86.5, 'Scenes cloudier than this are dropped before anything is '
                           'computed.'),
        ],
    ),
    'hydroperiod-tab': Figure(
        name='hydroperiod-tab',
        alt='The Hydroperiod tab of the panel',
        caption='The main product: how many days each pixel held water during one cycle.',
        marks=[
            Mark(28, 36.3, 'Which layer of the result to draw. Normalized is the one to open '
                           'on — it corrects the count for how many valid observations the '
                           'pixel actually had.'),
            Mark(28, 58.3, 'Which cycle. It has to fall inside the period above.'),
            Mark(3, 81.2, 'Sends the request. Earth Engine computes tile by tile as the map '
                          'draws, so the picture fills in gradually.'),
        ],
    ),
    'hydroperiod-map': Figure(
        name='hydroperiod-map',
        alt='A normalized hydroperiod drawn over a wetland, deep blue where water stood '
            'longest and pale where it barely stood at all',
        caption='One cycle of Lake Fertő. The scale runs from nothing to a whole year, and '
                'the wetland is read at a glance: the permanent water, the fringe that dries, '
                'and the ground that only ever catches a flood.',
        ext='jpg',
        marks=[
            Mark(58, 56.8, 'Deep blue: water for most of the cycle, or all of it.'),
            Mark(40, 72.4, 'Pale: flooded, but only briefly.'),
            Mark(95, 8, 'Every layer can be turned off here without being removed.'),
        ],
    ),
    'hydroperiod-scheme': Figure(
        name='hydroperiod-scheme',
        alt='A diagram of one hydrological cycle: the scenes on a timeline, the cut points '
            'halfway between them, and the days each scene is credited with',
        caption='How the days are counted. Scenes are not evenly spaced, so each one is made '
                'to answer for the stretch of time around it, out to the halfway point with '
                'the scene before and the scene after. The diagram, and the method, are '
                'Phydroperiod\'s (García Díaz & Bustamante Díaz, EBD-CSIC).',
    ),
    'layer-bar': Figure(
        name='layer-bar',
        alt='The bar under the map showing the active layer, its legend and its opacity slider',
        caption='Every layer you add appears here and in the layer switcher on the map.',
        ext='jpg',
        marks=[
            Mark(4, 35, 'What the layer is, and over which area it was computed.'),
            Mark(45, 35, 'The colour scale, with the values at each end.'),
            Mark(89, 35, 'Fades the layer to see the imagery underneath.'),
            Mark(95, 35, 'Removes this one, or clears them all.'),
        ],
    ),
    'anomalies-tab': Figure(
        name='anomalies-tab',
        alt='The Anomalies tab of the panel',
        caption='How unusual a cycle was, in days above or below a reference mean.',
        marks=[
            Mark(28, 37.7, 'The reference: the mean of the years you asked for, or the '
                           'sensor\'s entire archive. The second is far more expensive.'),
            Mark(28, 53.2, 'Whether to draw the reference mean itself or the anomaly of one '
                           'cycle against it.'),
            Mark(28, 68.1, 'Which cycle the anomaly is of.'),
        ],
    ),
    'anomalies-map': Figure(
        name='anomalies-map',
        alt='An anomaly layer over a wetland: blue where the cycle was wetter than the '
            'reference mean, red where it was drier',
        caption='The same wetland, one cycle against the mean of the period. The scale runs '
                'from −180 to +180 days, and most of the ground sits near the middle: an '
                'anomaly map is mostly a map of where nothing unusual happened.',
        ext='jpg',
        marks=[
            Mark(30.5, 26.3, 'Blue: wetter than the reference, in days.'),
            Mark(65, 59.2, 'Red: drier than the reference.'),
            Mark(43, 68, 'Pale ground held water for about as long as it usually does.'),
        ],
    ),
    'twi-tab': Figure(
        name='twi-tab',
        alt='The TWI tab and the terrain wetness index on the map',
        caption='Where water tends to gather, from the shape of the ground alone. It uses '
                'neither the sensor nor the period beside it.',
        ext='jpg',
        marks=[
            Mark(9, 44.7, 'The elevation model. The 30 m hybrid sharpens the slope, but flow '
                          'accumulation still comes from MERIT at about 90 m.'),
            Mark(63, 52, 'High values are hollows and valley floors; low values are slopes '
                         'and ridges.'),
        ],
    ),
    'stats-tab': Figure(
        name='stats-tab',
        alt='The Stats tab, with a file of polygons chosen',
        caption='Measures whatever product you name, over points or polygons of your own.',
        marks=[
            Mark(28, 39.1, 'A .geojson, .json or zipped shapefile of points or polygons.'),
            Mark(28, 58.2, 'How finely to sample. Left empty it uses the product\'s own '
                           'resolution.'),
            Mark(28, 77.4, 'Which product to measure — the tabs\' own settings decide what '
                           'that means.'),
            Mark(3, 89.9, 'Computes and waits, up to a thousand features.'),
            Mark(30, 89.9, 'Hands the same job to Earth Engine as a CSV in Drive, which is '
                           'the way to do it above that.'),
        ],
    ),
    'stats-table': Figure(
        name='stats-table',
        alt='The left half of the table of zonal statistics under the map, with one row '
            'per polygon',
        caption='The table appears under the map, where it has the width to be read, and '
                'survives switching tabs. This is its left half: min, max, standard '
                'deviation, pixel count and the Download CSV button follow to the right.',
        marks=[
            Mark(34, 20, 'What was measured and at what scale.'),
            Mark(14, 67, 'One row per feature. Points give the pixel value; polygons give '
                         'mean, median, min, max, standard deviation and pixel count.'),
        ],
    ),
    'export-tab': Figure(
        name='export-tab',
        alt='The Export tab',
        caption='Exports run on your own Earth Engine account and land in your own Drive.',
        marks=[
            Mark(25, 43.2, 'Either one GeoTIFF per cycle of the period, or the single product '
                           'currently on screen.'),
            Mark(25, 57.4, 'The folder in Drive. It is created if it does not exist.'),
            Mark(25, 71.3, 'The pixel size of the exported file.'),
            Mark(3, 85.5, 'Queues the tasks. They run on Earth Engine\'s time, not while '
                            'you wait.'),
        ],
    ),
    'inspector': Figure(
        name='inspector',
        alt='The popup the value reader opens where the map was clicked, listing the '
            'bands of the layer and their values at that pixel',
        caption='Reads the layer already on the map at one point — the same image that is '
                'drawn, not whatever the panel has selected by now. The reader is the '
                'eyedropper under the drawing tools; once it is on, the pointer becomes a '
                'crosshair and a click asks rather than pans.',
        ext='jpg',
        marks=[
            Mark(35, 35.2, 'The value at that pixel, band by band. A pixel the product '
                           'says nothing about reads "no data (masked)", which is not the '
                           'same as a hydroperiod of zero days.'),
            Mark(68, 39.5, 'Where you clicked, and the resolution the value was read at.'),
        ],
    ),
    'compare': Figure(
        name='compare',
        alt='Two layers compared with a draggable divider across the map',
        caption='Splits the map between two layers you have already added. Nothing here goes '
                'back to Earth Engine, so it is instant.',
        ext='jpg',
        marks=[
            Mark(9, 23, 'The two layers, left and right. They have to be different ones.'),
            Mark(63, 13, 'The divider. Drag it across the map.'),
            Mark(10, 33, 'Ends the split. Both layers stay on the map.'),
        ],
    ),
    'log': Figure(
        name='log',
        alt='The log at the foot of the panel, with several entries',
        caption='The log narrates every request. When something fails, this is where it says '
                'so and why.',
        marks=[
            Mark(6, 45, 'The time each thing happened.'),
            Mark(45, 31, 'What was asked and what came back: requests plain, results in '
                         'green, errors in red. They say what to change, not just that '
                         'something broke.'),
            Mark(93, 10, 'Empties the log. Nothing on the map goes with it.'),
        ],
    ),
}
