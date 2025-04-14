import bpy

#function definition
def MoveVertex():
    bpy.data.objects["Cube"].data.vertices[0].co.x += 1.0

for i in range(10):
    MoveVertex()