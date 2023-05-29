# IPP-2023
Solution to IPP project at FIT VUT, 2023.

parse.php parses program written in IPPcode23 to xml, which is later interpreted by interpret.py

## usage:
```console
php8.1 parse.php < example1.src | python3 interpret.py --input=example1.in
```