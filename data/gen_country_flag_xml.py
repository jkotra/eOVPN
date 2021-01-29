import os

for flag in os.listdir("country_flags/svg/"):

    print("<file>{}</file>".format(os.path.join("country_flags", "svg", flag)))
