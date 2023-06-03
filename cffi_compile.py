import cffi
import pathlib
import os
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--library", type=str, required=True)
parser.add_argument("--header", type=str, required=True)
args = parser.parse_args()

ffi = cffi.FFI()

workdir = pathlib.Path(args.library).parent
os.chdir(workdir)

output = workdir / ("_" + pathlib.Path(args.library).name)
h_file = pathlib.Path(args.header)

with open(h_file) as h_file:
    ffi.cdef(h_file.read())

ffi.set_source(output.stem, 
                f"#include \"{h_file.name}\"",
                libraries=[pathlib.Path(args.library).stem.replace("lib","")],
                library_dirs=[str(workdir)],
                extra_link_args=[f"-Wl,-rpath=$ORIGIN,-I{str(h_file)}"])

if __name__ == "__main__":    
    print("cffi library =>", ffi.compile(target=str(output)))
