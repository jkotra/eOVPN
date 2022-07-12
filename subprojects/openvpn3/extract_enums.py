from openvpn3.constants import StatusMajor, StatusMinor

f = open("openvpn3.h", "w+")

for (k,v) in StatusMajor.__members__.items():
    print(f"#define MAJOR_{k} {v.value}")
    f.write(f"#define MAJOR_{k} {v.value}\n")

for (k,v) in StatusMinor.__members__.items():
    print(f"#define MINOR_{k} {v.value}")
    f.write(f"#define MINOR_{k} {v.value}\n")

f.close()
print("written to file")