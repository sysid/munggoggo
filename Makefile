# You can set these variables from the command line, and also from the environment for the first two.
SOURCEDIR     = source
BUILDDIR      = build
TESTDIR       = munggoggo/tests
MAKEFILE_LIST = /tmp/makefile_list.txt
MAKE          = make

.PHONY: all help docs clean

# Put it first so that "make" without argument is like "make help".
help:
	@echo "$(MAKE) [all,docs,clean,bump,release]"

default: all

#all: unit
all: clean release docs

unit:
	py.test "$(TESTDIR)"

docs:
	#rm -rf docs/build/
	make -C docs/ clean
	make -C docs/ html
	cp docs/source/index.rst README.rst

clean:
	@echo "Cleaning up..."
	#git clean -Xdf
	rm -rf docs/build

bump:
	bump2version --dry-run --allow-dirty --verbose patch
	@echo "use bump! to confirm"

bump!:
	bump2version --allow-dirty --verbose patch

release:
	bump2version --allow-dirty --verbose release
