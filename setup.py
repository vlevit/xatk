from setuptools import setup
from setuptools.dist import Distribution


class PureDistribution(Distribution):
    def is_pure(self):
        return True


def read(name):
    with open(name) as f:
        return f.read()


setup(
    name='xatk',
    version='0.2.2',
    packages=[],
    include_package_data=True,
    zip_safe=False,
    platforms=['linux', 'freebsd', 'openbsd', 'netbsd'],
    scripts=[
        'xatk'
    ],
    install_requires=[
        "python-xlib>=0.15rc1"
    ],
    # metadata for upload to PyPI
    author='Vyacheslav Levit',
    author_email='dev@vlevit.org',
    description='keyboard-driven window switcher for X11',
    long_description=read('README.rst'),
    license='GPL',
    keywords='X11 keyboard windows',
    url='http://github.com/vlevit/xatk/',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Desktop Environment :: Window Managers'
    ],
    distclass=PureDistribution,
)
