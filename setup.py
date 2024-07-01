#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Cython.Build import cythonize
from Cython.Build.Dependencies import default_create_extension
from Cython.Compiler import Options
from Cython.Distutils import build_ext
from pysam import get_include as pysam_get_include
from setuptools import find_packages, setup
from setuptools.extension import Extension


def create_extention_no_metadata(template, kwds):
    return default_create_extension(template, kwds)[0], None


Options.docstrings = (
    False  # Don't use Cython docstrings to keep files stable for hashing
)

extra_compile_args = ["-Wno-unused-function"]
extensions = [
    Extension(
        "aldy.indelpost.variant",
        ["aldy/indelpost/variant.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.utilities",
        ["aldy/indelpost/utilities.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.pileup",
        ["aldy/indelpost/pileup.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.varaln",
        ["aldy/indelpost/varaln.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.contig",
        ["aldy/indelpost/contig.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.local_reference",
        ["aldy/indelpost/local_reference.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.softclip",
        ["aldy/indelpost/softclip.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.localn",
        ["aldy/indelpost/localn.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.gappedaln",
        ["aldy/indelpost/gappedaln.pyx"],
        include_dirs=pysam_get_include(),
        extra_compile_args=extra_compile_args,
    ),
    Extension(
        "aldy.indelpost.sswpy",
        sources=["aldy/indelpost/sswpy.pyx", "aldy/indelpost/ssw.c"],
        extra_compile_args=extra_compile_args,
    ),
]


exec(open("aldy/version.py").read())

setup(
    name="aldy",
    version=__version__,
    description="A tool for allelic decomposition (haplotype reconstruction) "
    + "and exact genotyping of highly polymorphic and structurally variant genes",
    url="http://aldy.csail.mit.edu/",
    author="Ibrahim Numanagić",
    author_email="inumanag@mit.edu",
    download_url="https://github.com/inumanag/aldy/tarball/master",
    license="Aldy/IURTC License. Free for academic/non-commercial use.",
    keywords=["cyp2d6", "adme", "genotyping", "illumina", "pgrnseq", "getrm", "allele"],
    install_requires=[
        "pyyaml",
        "logbook",
        "pysam",
        "pytest",
        "ortools",
        "natsort",
        "mappy",
        "numpy",
        "cython",
    ],
    entry_points={"console_scripts": ["aldy = aldy.__main__:console"]},
    packages=find_packages(),
    package_data={
        "aldy.resources": ["*.rst", "aldy/resources/*.rst"],
        "aldy.resources.genes": [
            "*.yml",
            "aldy/resources/genes/*.yml",
            "aldy/resources/genes/pharmacoscan/*.yml",
        ],
        "aldy.resources.profiles": ["*.yml", "aldy/resources/profiles/*.yml"],
        "aldy.tests.resources": [
            "*.json",
            "aldy/tests/resources/*.json",
            "*.bai",
            "aldy/tests/resources/*.bai",
            "*.bam",
            "aldy/tests/resources/*.bam",
            "*.expected",
            "aldy/tests/resources/*.expected",
            "*.yml",
            "aldy/tests/resources/*.yml",
            "aldy/tests/resources/pharmacoscan/*.yml",
            "*.profile",
            "aldy/tests/resources/*.profile",
            "*.hg38",
            "aldy/tests/resources/*.hg38",
            "*.vcf",
            "aldy/tests/resources/*.vcf",
            "*.gz",
            "aldy/tests/resources/*.gz",
            "*.tbi",
            "aldy/tests/resources/*.tbi",
        ],
        "aldy.indelpost": [
            "*.pyx",
            "aldy/indelpost/*.pyx",
            "*.pxd",
            "aldy/indelpost/*.pxd",
            "*.h",
            "aldy/indelpost/ssw.h",
            "aldy/indelpost/sse2neon.h",
        ],
    },
    cmdclass={"build_ext": build_ext},
    ext_modules=cythonize(
        extensions,
        create_extension=create_extention_no_metadata,
        compiler_directives={
            "language_level": "3",
            "emit_code_comments": False,
        },
    ),
    test_suite="pytest-runner",
    tests_require=["pytest"],
)
