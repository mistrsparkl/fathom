@rem (stellanova.py is imported, not run, so Python keeps it ready-made: each run starts sooner)
@py -3 -c "import sys; sys.path[0] = sys.argv.pop(1); import stellanova; sys.exit(stellanova.main(sys.argv))" "%~dp0." %*
