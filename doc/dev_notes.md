## Developer Notes for LifePIM Desktop

Notes for developers.

## Developing locally on your PC

### Setup local environment

1. make a new blank directory

2. setup a git repository

```
git init lifepim
```

3. get the source code

```
git pull https://github.com/acutesoftware/lifepim.git
```

4. get additional libraries

```
pip install pycalendar
```

### Coding standards

1. PEP8
2. no calls to external API's from any core code
3. no cryptic looking code

### Uploading changes

make the changes locally, including tests then commit

NOTE - steps below are for master branch only (Duncans notes - fix this for merging)

```
git add [yourfile].py
git commit -m "useful message"
git remote add origin https://github.com/acutesoftware/lifepim.git
git push --set-upstream origin master
```



### Interfacing to other apps / libraries
Core project remains open source

You can add in your own libraries (any license, seeing you are running it yourself) and call them from the interface

TODO


