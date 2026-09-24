from consumer import transform
for value in (-3, 0, 2):
    actual = transform(value)
    assert actual == value * 2, (value, actual)
print("PASS: three consumer behavior assertions")
