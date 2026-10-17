import bpy, math, os
bpy.ops.wm.read_factory_settings(use_empty=True)

def m(name, c):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*c, 1)
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (*c, 1)
            b.inputs["Emission Strength"].default_value = 1.5
    return mat

wm = m("w", (1,1,1))
ym = m("y", (1,0.8,0.1))

# backdrop
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 2, 0), rotation=(math.radians(90),0,0))
bg = bpy.context.active_object
bg.data.materials.append(m("bg", (0.05,0.07,0.1)))

# 方案A: rot(90,0,0)
cu = bpy.data.curves.new("A", "FONT")
cu.body = "方案A rot90 配载平衡"
cu.size = 0.5
o = bpy.data.objects.new("A", cu)
o.location = (-6, 0, 2)
o.rotation_euler = (math.radians(90), 0, 0)
bpy.context.collection.objects.link(o)
cu.materials.append(wm)

# 方案B: rot(90,0,0) + scale.x=-1
cu = bpy.data.curves.new("B", "FONT")
cu.body = "方案B scaleX-1 配载平衡"
cu.size = 0.5
o = bpy.data.objects.new("B", cu)
o.location = (-6, 0, 1)
o.rotation_euler = (math.radians(90), 0, 0)
o.scale = (-1, 1, 1)
bpy.context.collection.objects.link(o)
cu.materials.append(ym)

# 方案C: rot(90,0,180)
cu = bpy.data.curves.new("C", "FONT")
cu.body = "方案C rotZ180 配载平衡"
cu.size = 0.5
o = bpy.data.objects.new("C", cu)
o.location = (-6, 0, 0)
o.rotation_euler = (math.radians(90), 0, math.radians(180))
bpy.context.collection.objects.link(o)
cu.materials.append(wm)

# 方案D: rot(-90,0,0)
cu = bpy.data.curves.new("D", "FONT")
cu.body = "方案D rot-90 配载平衡"
cu.size = 0.5
o = bpy.data.objects.new("D", cu)
o.location = (-6, 0, -1)
o.rotation_euler = (math.radians(-90), 0, 0)
bpy.context.collection.objects.link(o)
cu.materials.append(ym)

bpy.ops.object.camera_add(location=(0, -12, 0.5), rotation=(math.radians(90), 0, 0))
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.object.light_add(type='SUN', location=(0,-5,10), rotation=(math.radians(45),0,0))
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x = 1200
sc.render.resolution_y = 600
sc.render.filepath = r"D:\AI-coding\XiaomiMiMoProjects\配载教学建模\output\preview\text_test.png"
bpy.ops.render.render(write_still=True)
print("ok")
