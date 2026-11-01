"""Reader `django-modele`: the model fields of a Python file (offline, synthetic source)."""
from __future__ import annotations

import unittest

import inventory
from inventory_django import FORMAT, read

SOURCE = '''from django.db import models
from django.utils.translation import gettext_lazy as _


class Ngo(models.Model):
    """Not a field."""
    name = models.CharField(_("Name"), max_length=100, help_text=_("Legal name"))
    note = models.TextField(null=True, blank=True)
    owner = models.ForeignKey("User", on_delete=models.CASCADE)
    tags = models.ManyToManyField(to=Tag)
    count: int = models.IntegerField(default=0)
    ignored = 5
    manager = NgoManager()

    class Meta:
        ordering = ["name"]

    def clean(self):
        self.x = models.CharField()


class Plain:
    value = 1
'''


class Reader(unittest.TestCase):
    def setUp(self):
        self.fields, self.cut = read(SOURCE)
        self.by = {f['cale']: f for f in self.fields}

    def test_only_field_assignments_of_a_class_are_fields(self):
        self.assertEqual(sorted(self.by), ['Ngo.count', 'Ngo.name', 'Ngo.note', 'Ngo.owner', 'Ngo.tags'])
        self.assertFalse(self.cut)

    def test_the_declared_type_the_null_flag_the_relation_and_the_description(self):
        self.assertEqual((self.by['Ngo.name']['tip_declarat'], self.by['Ngo.name']['obligatoriu'], self.by['Ngo.name']['descriere']), ('CharField', True, 'Legal name'))
        self.assertFalse(self.by['Ngo.note']['obligatoriu'])
        self.assertEqual((self.by['Ngo.owner']['tip_declarat'], self.by['Ngo.owner']['relatie']), ('ForeignKey', "'User'"))
        self.assertEqual(self.by['Ngo.tags']['relatie'], 'Tag')
        self.assertEqual(self.by['Ngo.count']['grup'], 'Ngo')

    def test_the_locator_covers_the_assignment(self):
        start, end = map(int, self.by['Ngo.note']['pointer'].removeprefix('char:').split('-'))
        self.assertEqual(SOURCE[start:end], 'note = models.TextField(null=True, blank=True)')

    def test_a_non_ascii_source_keeps_exact_offsets(self):
        text = '"""Ă î ș"""\nclass A(models.Model):\n    nume = models.CharField(help_text="ăâ")  # ț\n    x = models.IntegerField()\n'
        for field in read(text)[0]:
            start, end = map(int, field['pointer'].removeprefix('char:').split('-'))
            self.assertTrue(text[start:end].startswith(field['nume'] + ' ='))

    def test_a_syntax_error_and_a_file_without_a_field_are_errors(self):
        for text in ('class A(:\n', 'x = 1\n'):
            with self.assertRaises(ValueError):
                read(text)

    def test_the_same_path_twice_is_an_error(self):
        with self.assertRaises(ValueError):
            read('class A(models.Model):\n    a = models.IntegerField()\n    a = models.CharField()\n')

    def test_the_extension_selects_the_reader(self):
        fmt, fields, _ = inventory.parse_source(SOURCE, 'https://raw.example/x/models.py', 'text/plain', None)
        self.assertEqual((fmt, len(fields)), (FORMAT, 5))


if __name__ == '__main__':
    unittest.main()
