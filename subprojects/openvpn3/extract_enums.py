from openvpn3.constants import StatusMajor, StatusMinor
import pathlib

if pathlib.Path("openvpn3.h").exists():
    with open("openvpn3.h", "r") as header:
        if "#define MAJOR" in header:
            print("enums in header file already generated!")
            exit(0)

f = open("openvpn3.h", "a+")
f.write("\n")
for (k,v) in StatusMajor.__members__.items():
    print(f"#define MAJOR_{k} {v.value}")
    f.write(f"#define MAJOR_{k} {v.value}\n")

for (k,v) in StatusMinor.__members__.items():
    print(f"#define MINOR_{k} {v.value}")
    f.write(f"#define MINOR_{k} {v.value}\n")

f.close()
print("written to file")