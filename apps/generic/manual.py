"""The screenshots of the two manuals, and what each numbered mark on them points at.

The prose lives in the templates; this file holds only what the templates cannot say
tidily -- where every mark sits on top of its screenshot -- because that is the part
that gets adjusted most and is unreadable spread through the markup.

A mark is placed in percentages of the image, not pixels, so a screenshot retaken at a
different window size keeps its marks roughly in place. To find the numbers, open any
manual page with `?markers=1` and click on the screenshot: the position under the
pointer is written next to it, ready to be pasted here.

Screenshots go in `static/img/manual/` under the name each figure declares. Missing
ones are not an error: the page draws a placeholder naming the file it expects and
listing the marks it is waiting for, so an incomplete manual reads as a checklist of
what is left to capture rather than as a page of broken images.
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

    @property
    def path(self):
        return f'img/manual/{self.name}.png'


# --------------------------------------------------------------------------- #
# Manual 1 -- the Earth Engine account                                         #
# --------------------------------------------------------------------------- #

EARTH_ENGINE = {
    'cloud-onboarding': Figure(
        name='cloud-onboarding',
        alt='The Earth Engine page of the Google Cloud console, before any project exists',
        caption='The Earth Engine setup page of the Cloud console. It creates the project and '
                'registers it in one pass, which is why it is worth starting here rather than '
                'making the project by hand.',
        marks=[
            Mark(50, 30, 'The project this page is about. Empty on a first visit — the next '
                         'step is what fills it in.'),
            Mark(50, 62, 'Starts the questionnaire that decides whether the project is '
                         'commercial or noncommercial.'),
        ],
    ),
    'register-noncommercial': Figure(
        name='register-noncommercial',
        alt='The registration questionnaire with the noncommercial option selected',
        caption='The registration questionnaire. Everything the consortium does with this '
                'application falls under noncommercial use.',
        marks=[
            Mark(30, 34, 'Unpaid, noncommercial usage. This is the branch to take: it needs no '
                         'billing account and costs nothing.'),
            Mark(30, 58, 'The kind of organisation. For the EBD-CSIC and the university '
                         'partners this is academic or research.'),
            Mark(72, 88, 'Confirms the answers. Eligibility is checked against what is '
                         'declared here, so it is worth reading rather than clicking through.'),
        ],
    ),
    'project-id': Figure(
        name='project-id',
        alt='The Cloud console project selector, showing the project ID next to its name',
        caption='The project ID is not the project name. The application asks for the ID: '
                'lowercase, hyphenated, often with digits appended by Google.',
        width='narrow',
        marks=[
            Mark(28, 40, 'The display name, which you chose and which the application does '
                         'not want.'),
            Mark(72, 40, 'The ID. This is what goes into the connection form.'),
        ],
    ),
    'enable-api': Figure(
        name='enable-api',
        alt='The Earth Engine API page in the Cloud console API library, with the Enable button',
        caption='The Earth Engine API on the project. The registration page usually turns it '
                'on for you; this is where to check when the connection later refuses.',
        marks=[
            Mark(24, 22, 'The project the button applies to. Check it before clicking: the '
                         'console remembers whichever project you last used, which is not '
                         'always this one.'),
            Mark(24, 62, 'Enables the API. Once on, it reads "Manage" instead.'),
        ],
    ),
    'tier': Figure(
        name='tier',
        alt='The Earth Engine configuration page showing the project tier and its monthly quota',
        caption='The tier decides how much computation the project gets each month. New '
                'noncommercial projects land on Community.',
        marks=[
            Mark(30, 40, 'The current tier and its monthly allowance of EECU-hours.'),
            Mark(30, 66, 'How much of this month\'s quota is already spent. It resets on the '
                         'first of the month.'),
            Mark(72, 40, 'Where to move to the Contributor tier, which is still free but '
                         'wants a billing account attached to the project.'),
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
    'connect-form': Figure(
        name='connect-form',
        alt='The Earth Engine connection screen, asking for a Google Cloud project ID',
        caption='The connection screen, reached from the warning on the home page or from the '
                'Earth Engine badge in the bar at the top.',
        marks=[
            Mark(50, 44, 'The project ID from step 3 — the ID, not the display name.'),
            Mark(50, 66, 'Opens the Google authorisation step.'),
        ],
    ),
    'authorize': Figure(
        name='authorize',
        alt='The Google authorisation page showing the code to copy back into the application',
        caption='Google\'s own authorisation page. It ends by showing a long code, which is '
                'what the application is waiting for.',
        marks=[
            Mark(50, 30, 'The Google account being authorised. Make sure it is the one that '
                         'owns the project.'),
            Mark(50, 74, 'The authorisation code. Copy the whole of it.'),
        ],
    ),
    'paste-code': Figure(
        name='paste-code',
        alt='The application waiting for the authorisation code to be pasted',
        caption='Back in the application, the pasted code is exchanged for a token that is '
                'stored encrypted against your account.',
        marks=[
            Mark(50, 34, 'The same link, in case the tab was closed before the code appeared.'),
            Mark(50, 60, 'Where the code goes.'),
            Mark(50, 78, 'Completes the connection.'),
        ],
    ),
    'connected': Figure(
        name='connected',
        alt='The top bar of the application showing the green Earth Engine badge with the project name',
        caption='Connected. The badge names the project every computation will run on, and '
                'clicking it leads back to the screen that can disconnect it.',
        marks=[
            Mark(80, 50, 'The connected project. If this is missing, nothing will compute.'),
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
            Mark(50, 30, 'The outline of every wetland in the study area, drawn small.'),
            Mark(30, 62, 'How many areas it holds, Ramsar wetlands and eLTER sites together.'),
            Mark(30, 78, 'Opens the workspace, which is where the whole of the rest of this '
                         'manual happens.'),
        ],
    ),
    'workspace': Figure(
        name='workspace',
        alt='The workspace: the control panel on the left and the map on the right',
        caption='The workspace. The panel on the left says what to compute; the map on the '
                'right shows it. Below a wide screen the two stack, panel first.',
        marks=[
            Mark(22, 20, 'Which area to work on, chosen in two steps.'),
            Mark(22, 46, 'The time series: the same sensor, period, index and threshold feed '
                         'every tab that needs them.'),
            Mark(22, 66, 'The five tabs, one per product.'),
            Mark(22, 88, 'The log, which narrates every request and is where errors show up.'),
            Mark(70, 30, 'The map. Wetlands in blue-grey, eLTER sites in dashed purple, the '
                         'study area outline in gold.'),
            Mark(93, 14, 'The layer switcher: basemaps, and every layer you add.'),
            Mark(58, 14, 'Drawing tools, and below them the value reader.'),
        ],
    ),
    'area-source': Figure(
        name='area-source',
        alt='The area picker, with the source dropdown open',
        caption='The area is chosen in two steps because the three sources together are far '
                'too many entries for one dropdown.',
        width='narrow',
        marks=[
            Mark(60, 26, 'Where the area comes from: the basin\'s Ramsar wetlands, the eLTER '
                         'sites that fall inside it, or a shape of your own.'),
            Mark(60, 62, 'Then which one. Picking here also frames the map on it.'),
        ],
    ),
    'draw': Figure(
        name='draw',
        alt='A polygon being drawn on the map with the drawing tools',
        caption='A drawn shape overrides whatever the dropdown holds: it is the more '
                'deliberate act of the two, so the application prefers it.',
        marks=[
            Mark(12, 26, 'Polygon and rectangle. Either one produces the area to analyse.'),
            Mark(12, 52, 'Edit and delete what has been drawn. Deleting it hands the choice '
                         'back to the dropdown.'),
            Mark(55, 55, 'The shape itself, in amber to tell it from the wetlands underneath.'),
        ],
    ),
    'time-series': Figure(
        name='time-series',
        alt='The time series block of the panel',
        caption='These six fields define the series every product is built from. Changing the '
                'sensor rewrites what the other fields will accept.',
        width='narrow',
        marks=[
            Mark(62, 12, 'Sentinel-2 for detail, Landsat for depth of record, MODIS for very '
                         'large areas.'),
            Mark(62, 34, 'The period, in hydrological years. A cycle labelled 2021 runs from '
                         '1 September 2021 to 1 September 2022.'),
            Mark(62, 58, 'The water index. MNDWI is the sensible default and works on all '
                         'three sensors.'),
            Mark(62, 72, 'Above this value a pixel counts as water.'),
            Mark(62, 88, 'Scenes cloudier than this are dropped before anything is computed.'),
        ],
    ),
    'hydroperiod-tab': Figure(
        name='hydroperiod-tab',
        alt='The Hydroperiod tab with a computed layer on the map',
        caption='The main product: how many days each pixel held water during one cycle.',
        marks=[
            Mark(22, 30, 'Which layer of the result to draw. Normalized is the one to open '
                         'on — it corrects the count for how many valid observations the '
                         'pixel actually had.'),
            Mark(22, 46, 'Which cycle. It has to fall inside the period above.'),
            Mark(22, 62, 'Sends the request. Earth Engine computes tile by tile as the map '
                         'draws, so the picture fills in gradually.'),
            Mark(70, 40, 'The result. Blank ground never flooded during the period and is '
                         'left undrawn rather than painted as zero.'),
        ],
    ),
    'layer-bar': Figure(
        name='layer-bar',
        alt='The bar under the map showing the active layer, its legend and its opacity slider',
        caption='Every layer you add appears here and in the layer switcher on the map.',
        marks=[
            Mark(12, 50, 'What the layer is, and over which area it was computed.'),
            Mark(42, 50, 'The colour scale, with the values at each end.'),
            Mark(70, 50, 'Fades the layer to see the imagery underneath.'),
            Mark(90, 50, 'Removes this one, or clears them all.'),
        ],
    ),
    'anomalies-tab': Figure(
        name='anomalies-tab',
        alt='The Anomalies tab and an anomaly layer on the map',
        caption='How unusual a cycle was, in days above or below a reference mean.',
        marks=[
            Mark(22, 26, 'The reference: the mean of the years you asked for, or the sensor\'s '
                         'entire archive. The second is far more expensive.'),
            Mark(22, 42, 'Whether to draw the reference mean itself or the anomaly of one '
                         'cycle against it.'),
            Mark(70, 40, 'Blue is wetter than the reference, red is drier.'),
        ],
    ),
    'twi-tab': Figure(
        name='twi-tab',
        alt='The TWI tab and the terrain wetness index on the map',
        caption='Where water tends to gather, from the shape of the ground alone. It uses '
                'neither the sensor nor the period beside it.',
        marks=[
            Mark(22, 30, 'The elevation model. The 30 m hybrid sharpens the slope, but flow '
                         'accumulation still comes from MERIT at about 90 m.'),
            Mark(70, 40, 'High values are hollows and valley floors; low values are slopes '
                         'and ridges.'),
        ],
    ),
    'stats-tab': Figure(
        name='stats-tab',
        alt='The Stats tab, with a file of polygons chosen',
        caption='Measures whatever product you name, over points or polygons of your own.',
        width='narrow',
        marks=[
            Mark(62, 22, 'A .geojson, .json or zipped shapefile of points or polygons.'),
            Mark(62, 44, 'How finely to sample. Left empty it uses the product\'s own '
                         'resolution.'),
            Mark(62, 62, 'Which product to measure — the tabs\' own settings decide what that '
                         'means.'),
            Mark(30, 84, 'Computes and waits, up to a thousand features.'),
            Mark(72, 84, 'Hands the same job to Earth Engine as a CSV in Drive, which is the '
                         'way to do it above that.'),
        ],
    ),
    'stats-table': Figure(
        name='stats-table',
        alt='The table of zonal statistics under the map',
        caption='The table appears under the map, where it has the width to be read, and '
                'survives switching tabs.',
        marks=[
            Mark(20, 18, 'What was measured and at what scale.'),
            Mark(80, 18, 'Downloads exactly these rows as a CSV, without going through Drive.'),
            Mark(30, 55, 'One row per feature. Points give the pixel value; polygons give '
                         'mean, median, min, max, standard deviation and pixel count.'),
        ],
    ),
    'export-tab': Figure(
        name='export-tab',
        alt='The Export tab',
        caption='Exports run on your own Earth Engine account and land in your own Drive.',
        width='narrow',
        marks=[
            Mark(62, 20, 'Either one GeoTIFF per cycle of the period, or the single product '
                         'currently on screen.'),
            Mark(62, 42, 'The folder in Drive. It is created if it does not exist.'),
            Mark(62, 58, 'The pixel size of the exported file.'),
            Mark(35, 84, 'Queues the tasks. They run on Earth Engine\'s time, not while you '
                         'wait.'),
        ],
    ),
    'inspector': Figure(
        name='inspector',
        alt='The value reader, showing a popup with the values of the layer at one point',
        caption='Reads the layer already on the map at one point — the same image that is '
                'drawn, not whatever the panel has selected by now.',
        marks=[
            Mark(12, 30, 'Turns reading on. The pointer becomes a crosshair and clicks stop '
                         'panning the map.'),
            Mark(55, 50, 'The values at that pixel, band by band, with the coordinates '
                         'underneath.'),
        ],
    ),
    'compare': Figure(
        name='compare',
        alt='Two layers compared with a draggable divider across the map',
        caption='Splits the map between two layers you have already added. Nothing here goes '
                'back to Earth Engine, so it is instant.',
        marks=[
            Mark(22, 30, 'The two layers, left and right. They have to be different ones.'),
            Mark(50, 50, 'The divider. Drag it across the map.'),
        ],
    ),
    'log': Figure(
        name='log',
        alt='The log at the foot of the panel, with several entries',
        caption='The log narrates every request. When something fails, this is where it says '
                'so and why.',
        marks=[
            Mark(15, 40, 'The time each thing happened.'),
            Mark(55, 62, 'Errors in red. They say what to change, not just that something '
                         'broke.'),
        ],
    ),
}
