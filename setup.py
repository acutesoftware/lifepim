from setuptools import setup

setup(
    name='lifepim',
    version='0.0.4',
    author='Duncan Murray',
    author_email='djmurray@gmail.com',
    packages=['lifepim', 'lifepim.web_app'],
    url='https://github.com/acutesoftware/lifepim',
    license='GNU General Public License v3 (GPLv3)',
    description='Personal Information Manager for Life',
    long_description='lets you quickly manage and find everything - all lists, ideas, and notes, tasks, calendar events, logs, ETL jobs, images, music, videos, programs, etc.',
    install_requires=[
          'nose >= 1.0',
          'AIKIF >= 0.1.3',
          'flask >= 0.10.1',
          'flask-httpauth >= 2.3.0',
          'flask-restful >= 0.3.1'
    ],
    classifiers = [
    'Development Status :: 1 - Planning',
    'Environment :: Web Environment',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Intended Audience :: Developers',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Office/Business :: News/Diary',
    ],

)


