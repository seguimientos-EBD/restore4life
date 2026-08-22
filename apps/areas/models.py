from django.contrib.gis.db import models


class StudyArea(models.Model):
    """Working zone: a name and, optionally, the outline that bounds it.

    The wetlands supply the detail; the boundary is what the map opens on and refuses
    to let you pan out of — the Danube basin, in the case this app was built for.
    """

    name = models.CharField(max_length=255, verbose_name='name')
    boundary = models.GeometryField(
        srid=4326, null=True, blank=True, verbose_name='boundary',
        help_text='Outline the map is framed by. Without it the map frames the wetlands.',
    )

    class Meta:
        verbose_name = 'Study area'
        verbose_name_plural = 'Study areas'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Wetland(models.Model):
    """Each of the areas the hydroperiod can be computed on, whatever its source.

    Two registries feed this table and they are told apart by `kind`: the Ramsar
    wetlands of the basin, and the eLTER sites that intersect it. They live together
    because what the app does with one it does with the other -- it is a name and an
    outline to hand to Earth Engine -- and keeping them apart would mean a second copy
    of every view, endpoint and lookup for no gain.

    The non-geometric fields are those of the Danube Ramsar shapefile, with the
    `.dbf` column names in the comment: they come truncated to ten characters and
    without accents, so they are stored here under readable names. An eLTER site fills
    in only `name`, `country` and `deims_id`; the Ramsar columns stay empty.
    """

    class Kind(models.TextChoices):
        RAMSAR = 'ramsar', 'Ramsar site'
        ELTER = 'elter', 'eLTER site'

    study_area = models.ForeignKey(StudyArea, on_delete=models.CASCADE, related_name='wetlands')
    kind = models.CharField(
        max_length=16, choices=Kind.choices, default=Kind.RAMSAR, db_index=True, verbose_name='kind',
    )
    name = models.CharField(max_length=255, verbose_name='name')                     # officialna
    fid = models.IntegerField(null=True, blank=True, verbose_name='FID')             # fid
    v_idris = models.BigIntegerField(null=True, blank=True, verbose_name='Idris ID')  # v_idris
    ramsar_id = models.IntegerField(null=True, blank=True, verbose_name='Ramsar ID')  # ramsarid
    iso3 = models.CharField(max_length=3, blank=True, verbose_name='ISO3')           # iso3
    country = models.CharField(max_length=255, blank=True, verbose_name='country')   # country_en
    official_area = models.FloatField(null=True, blank=True, verbose_name='official area (ha)')  # area_off
    # DEIMS-SDR record of an eLTER site, which is the id it is known by everywhere else.
    # It is the full URL rather than the bare UUID because that is what DEIMS hands out.
    deims_id = models.URLField(blank=True, verbose_name='DEIMS-SDR id')
    geom = models.GeometryField(srid=4326, verbose_name='geometry')

    class Meta:
        verbose_name = 'Area'
        verbose_name_plural = 'Areas'
        ordering = ('name',)

    def __str__(self):
        return self.name
