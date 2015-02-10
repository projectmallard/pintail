# Pintail - Build web sites from Mallard sources

Pintail is a tool that automates building entire web sites from Mallard sources.
Normally, a Mallard document consists of all the pages within a single directory.
Pages can refer to each other by ID using the `xref` attribute of the `link`
element. Pintail allows multiple directories, and extends the `xref` attribute
to allow referencing pages in other directories.

## Install Pintail

Pintail uses Python setuptools to build and install. Pintail is Python-3-only,
so to build and install:

```
python3 setup.py build
sudo python3 setup.py install
```

Or to get the latest version uploaded to pypi:

```
pip-python3 install pintail
```

Pintail requires `yelp-xsl` for transforming Mallard pages into HTML. This is
available on all major Linux distributions, and is installed by default on
most. Use your distribution's package manager, or use MacPorts to install
`yelp-xsl` on Mac. (Future versions will download `yelp-xsl` automatically if
necessary. See issue #8.)

## Using Pintail

To start using Pintail, run `pintail init` in the top-level directory for your
site. This may be a new empty directory or a directory already populated with
Mallard page files. This command will create a sample `pintail.cfg` file. Edit
this file to customize your site.

Create Mallard page files. If you're new to Mallard, check out the [tutorials]
(http://projectmallard.org/about/learn/) on projectmallard.org. Anything you
can do in Mallard, you can do with Pintail. And since Pintail builds on the
extensive `yelp-xsl` stylesheets, any extensions supported by Yelp are also
supported by Pintail.

To build a site, run `pintail build`. This will build all HTML, CSS, and
JavaScript files, copy image and other files, and generate everything you
need to upload to your server. Images and videos found automatically by
looking in the Mallard page files. You can specify more files using the
`extra_files` configuration key.

You can also regenerate only particular parts of the site. For example,
you can use `pintail css` to build only the CSS files, which is useful
when iterating on the design. See `pintail --help` for more options.

You can also pass `--local` to build files more suitable for local viewing.
This automatically sets the site root to the build directory, and you can
specify different values for various configuration options.

## Configuration Reference

The Pintail configuration file is a simple INI file. Site-level options
are in the `[pintail]` group.

```ini
[pintail]
site_root = /
html_extension = .html
custom_xsl = mycustom.xsl
```

You can also override any site-level options in the `[local]` group.
These values will be used instead when you pass `--local`.

You can specify options for each directory by adding a group with
the directory's path. The path must begin and end with a slash.

```ini
[/downloads/]
extra_files = mypackage.zip
```

## Site Extensions

Pintail extends Mallard to allow referencing pages outside the same
directory. As with stock Mallard, all pages in a single directory
are part of a document, and so page IDs must be unique within each
directory. Page IDs to not have to be unique across an entire site.

To reference a page in a different directory, put the directory path
before the target page ID, starting with a slash, `xref="/about/learn/svg"`

Pintail also adds a type for the `links` element, `site-subdirs`.
(This should be changed to `site:subdirs`. See issue #9.) This will
create a list of links to the index page of each immediate subdirectory
of the directory of the current page.

