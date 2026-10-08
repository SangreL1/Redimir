# Generated manually to populate all habitual materials from Enaex matrix
from decimal import Decimal
from django.db import migrations

def poblar_catalogo_enaex(apps, schema_editor):
    CatalogoMaterialRetiro = apps.get_model('servicios', 'CatalogoMaterialRetiro')

    materiales = [
        # (Nombre, Categoria, Unidad, Factor_kg, Orden)
        ("Cartón", "Reciclaje", "kg", Decimal('0.00'), 1),
        ("Papel", "Reciclaje", "kg", Decimal('0.00'), 2),
        ("Botellas Plásticas / PET", "Reciclaje", "kg", Decimal('0.00'), 3),
        ("Film", "Reciclaje", "kg", Decimal('0.00'), 4),
        ("Latas de Aluminio", "Reciclaje", "kg", Decimal('0.00'), 5),
        ("Zuncho", "Metales", "kg", Decimal('0.00'), 6),
        ("Chatarra / Metales", "Metales", "kg", Decimal('0.00'), 7),
        ("Vidrio", "Reciclaje", "kg", Decimal('0.00'), 8),
        ("PP (Polipropileno)", "Reciclaje", "kg", Decimal('0.00'), 9),
        ("Barras de Perforación", "Metales", "kg", Decimal('0.00'), 10),
        ("Pallets", "Madera", "kg_un", Decimal('20.00'), 11),
        ("Pallets en Mal Estado", "Madera", "kg_un", Decimal('20.00'), 12),
        ("Pallets Plásticos", "Reciclaje", "kg_un", Decimal('15.00'), 13),
        ("Carretes de Madera", "Madera", "kg_un", Decimal('5.50'), 14),
        ("Carretes Plásticos", "Reciclaje", "kg_un", Decimal('2.50'), 15),
        ("Carretes Plásticos APD", "Reciclaje", "kg_un", Decimal('0.50'), 16),
        ("Tambores", "Envases", "kg_un", Decimal('10.00'), 17),
        ("Tambor Metálico", "Envases", "kg_un", Decimal('10.00'), 18),
        ("Tambores 50 Litros", "Envases", "kg_un", Decimal('2.50'), 19),
        ("Bidones 20 Litros", "Envases", "kg_un", Decimal('1.00'), 20),
        ("Bidones 25 Litros", "Envases", "kg_un", Decimal('1.20'), 21),
        ("Residuos Domésticos / Asimilables", "Domestico", "kg", Decimal('0.00'), 22),
        ("Residuos Generales / Mixto", "Otro", "kg", Decimal('0.00'), 23),
        ("Escombros / RESCON", "Otro", "kg", Decimal('0.00'), 24),
        ("Descarga y Acopio", "Otro", "kg", Decimal('0.00'), 25),
    ]

    for nombre, cat, um, factor, orden in materiales:
        # Buscar por nombre exacto o similar para actualizar
        mat = CatalogoMaterialRetiro.objects.filter(nombre__iexact=nombre).first()
        if not mat and nombre == "Residuos Generales / Mixto":
            mat = CatalogoMaterialRetiro.objects.filter(nombre__iexact="Residuos Generales").first()

        if mat:
            mat.nombre = nombre
            mat.categoria = cat
            mat.unidad_medida = um
            mat.peso_unitario_kg = factor
            mat.orden = orden
            mat.activo = True
            mat.save()
        else:
            CatalogoMaterialRetiro.objects.create(
                nombre=nombre,
                categoria=cat,
                unidad_medida=um,
                peso_unitario_kg=factor,
                orden=orden,
                activo=True
            )

def revertir_poblar_catalogo(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0004_catalogomaterialretiro_peso_unitario_kg'),
    ]

    operations = [
        migrations.RunPython(poblar_catalogo_enaex, revertir_poblar_catalogo),
    ]
