from django.contrib.gis.db import models


class Ambito(models.Model):
    """Zona de trabajo: solo un nombre. La geometría la ponen sus humedales."""

    nombre = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Ámbito'
        verbose_name_plural = 'Ámbitos'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre


class Humedal(models.Model):
    """Cada uno de los humedales del shapefile del ámbito.

    Los campos no geométricos son los del shapefile Ramsar del Danubio, con los
    nombres del `.dbf` en el comentario: vienen recortados a diez caracteres y sin
    acentos, así que aquí se guardan con nombres legibles.
    """

    ambito = models.ForeignKey(Ambito, on_delete=models.CASCADE, related_name='humedales')
    nombre = models.CharField(max_length=255)                                        # officialna
    fid = models.IntegerField(null=True, blank=True, verbose_name='FID')             # fid
    v_idris = models.BigIntegerField(null=True, blank=True, verbose_name='ID Idris')  # v_idris
    ramsarid = models.IntegerField(null=True, blank=True, verbose_name='ID Ramsar')  # ramsarid
    iso3 = models.CharField(max_length=3, blank=True, verbose_name='ISO3')           # iso3
    pais = models.CharField(max_length=255, blank=True, verbose_name='país')         # country_en
    area_oficial = models.FloatField(null=True, blank=True, verbose_name='área oficial (ha)')  # area_off
    geom = models.GeometryField(srid=4326, verbose_name='geometría')

    class Meta:
        verbose_name = 'Humedal'
        verbose_name_plural = 'Humedales'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre
