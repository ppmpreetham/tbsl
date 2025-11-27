import bpy
import json


def get_socket_default_value(socket):
    if not hasattr(socket, "default_value"):
        return None

    val = socket.default_value

    if val is None:
        return None

    if hasattr(val, "__class__") and val.__class__.__name__ in [
        "Image",
        "Object",
        "Collection",
        "Material",
        "Texture",
        "NodeTree",
    ]:
        return f"<{val.__class__.__name__}: {getattr(val, 'name', 'unnamed')}>"

    if hasattr(val, "__len__") and not isinstance(val, str):
        try:
            return list(val)
        except:
            return None

    if isinstance(val, (bool, int, float, str)):
        return val

    return None


def is_json_serializable(val):
    if val is None or isinstance(val, (bool, int, float, str)):
        return True
    if isinstance(val, (list, tuple)):
        return all(is_json_serializable(item) for item in val)
    if isinstance(val, dict):
        return all(is_json_serializable(v) for v in val.values())
    return False


def get_property_info(node, prop):
    prop_info = {
        "identifier": prop.identifier,
        "name": prop.name,
        "type": prop.type,
        "description": prop.description,
    }

    try:
        current_val = getattr(node, prop.identifier)

        if hasattr(current_val, "__class__") and current_val.__class__.__name__ in [
            "CurveMapping",
            "ColorMapping",
            "Image",
            "NodeTree",
            "Object",
            "Collection",
            "Material",
            "Texture",
        ]:
            prop_info["current_value"] = f"<{current_val.__class__.__name__}>"
        elif hasattr(current_val, "__len__") and not isinstance(current_val, str):
            try:
                val_list = list(current_val)
                if is_json_serializable(val_list):
                    prop_info["current_value"] = val_list
                else:
                    prop_info["current_value"] = None
            except:
                prop_info["current_value"] = None
        elif is_json_serializable(current_val):
            prop_info["current_value"] = current_val
        else:
            prop_info["current_value"] = None
    except:
        prop_info["current_value"] = None

    if prop.type == "ENUM":
        prop_info["enum_items"] = [item.identifier for item in prop.enum_items]

    if prop.type in ["FLOAT", "INT"]:
        if hasattr(prop, "array_length") and prop.array_length > 0:
            prop_info["array_length"] = prop.array_length
        if hasattr(prop, "hard_min"):
            prop_info["min"] = prop.hard_min
        if hasattr(prop, "hard_max"):
            prop_info["max"] = prop.hard_max

    return prop_info


def export_node_to_dict(node):
    node_data = {
        "name": node.name,
        "bl_idname": node.bl_idname,
        "type": node.type,
        "label": node.label,
        "location": list(node.location),
        "width": node.width,
        "height": node.height,
        "hide": node.hide,
        "mute": node.mute,
        "inputs": [],
        "outputs": [],
        "properties": {},
    }

    for inp in node.inputs:
        socket_data = {
            "name": inp.name,
            "identifier": inp.identifier,
            "type": inp.type,
            "default_value": get_socket_default_value(inp),
            "enabled": inp.enabled,
            "hide": inp.hide,
            "hide_value": inp.hide_value,
        }

        if inp.is_linked:
            socket_data["is_linked"] = True
            socket_data["links"] = []
            for link in inp.links:
                socket_data["links"].append(
                    {
                        "from_node": link.from_node.name,
                        "from_socket": link.from_socket.name,
                    }
                )

        node_data["inputs"].append(socket_data)

    for out in node.outputs:
        socket_data = {
            "name": out.name,
            "identifier": out.identifier,
            "type": out.type,
            "default_value": get_socket_default_value(out),
            "enabled": out.enabled,
            "hide": out.hide,
        }

        if out.is_linked:
            socket_data["is_linked"] = True
            socket_data["links"] = []
            for link in out.links:
                socket_data["links"].append(
                    {"to_node": link.to_node.name, "to_socket": link.to_socket.name}
                )

        node_data["outputs"].append(socket_data)

    parent_props = set()
    for base in type(node).__bases__:
        if hasattr(base, "bl_rna"):
            for prop in base.bl_rna.properties:
                parent_props.add(prop.identifier)

    for prop in node.bl_rna.properties:
        if prop.identifier in parent_props:
            continue
        if prop.identifier in ["rna_type", "dimensions", "internal_links"]:
            continue

        try:
            node_data["properties"][prop.identifier] = get_property_info(node, prop)
        except:
            pass

    if node.type == "VALTORGB":
        ramp_data = {
            "color_mode": node.color_ramp.color_mode,
            "hue_interpolation": node.color_ramp.hue_interpolation,
            "interpolation": node.color_ramp.interpolation,
            "elements": [],
        }
        for elem in node.color_ramp.elements:
            ramp_data["elements"].append(
                {
                    "position": elem.position,
                    "color": list(elem.color),
                    "alpha": elem.alpha,
                }
            )
        node_data["color_ramp"] = ramp_data

    elif node.type == "CURVE_RGB":
        curves_data = []
        for curve in node.mapping.curves:
            points = []
            for point in curve.points:
                points.append(
                    {"location": list(point.location), "handle_type": point.handle_type}
                )
            curves_data.append({"points": points})
        node_data["curves"] = curves_data

    elif node.type == "TEX_IMAGE" and node.image:
        node_data["image"] = {
            "name": node.image.name,
            "filepath": node.image.filepath,
            "size": list(node.image.size),
            "colorspace_settings": {"name": node.image.colorspace_settings.name},
        }

    return node_data


def export_material_nodes_to_json(material_name, filepath=None):
    material = bpy.data.materials.get(material_name)

    if not material:
        print(f"Material '{material_name}' not found")
        return None

    if not material.use_nodes:
        print(f"Material '{material_name}' doesn't use nodes")
        return None

    node_tree = material.node_tree

    export_data = {
        "material_name": material_name,
        "blend_method": material.blend_method,
        "use_backface_culling": material.use_backface_culling,
        "nodes": [],
        "links": [],
    }

    for node in node_tree.nodes:
        export_data["nodes"].append(export_node_to_dict(node))

    for link in node_tree.links:
        export_data["links"].append(
            {
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "from_socket_identifier": link.from_socket.identifier,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
                "to_socket_identifier": link.to_socket.identifier,
                "is_valid": link.is_valid,
                "is_hidden": link.is_hidden,
            }
        )

    if filepath:
        with open(filepath, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"Exported material to {filepath}")

    return export_data


def generate_master_shader_nodes_json(filepath=None):
    master_data = {
        "blender_version": ".".join(map(str, bpy.app.version)),
        "shader_nodes": {},
    }

    temp_mat = bpy.data.materials.new("_temp_master_export")
    temp_mat.use_nodes = True
    temp_tree = temp_mat.node_tree

    shader_node_types = []
    for attr_name in dir(bpy.types):
        attr = getattr(bpy.types, attr_name)
        if isinstance(attr, type) and issubclass(attr, bpy.types.Node):
            if attr_name.startswith("ShaderNode") or attr_name.startswith("ShaderNode"):
                if attr.is_registered_node_type():
                    shader_node_types.append(attr)

    print(f"Found {len(shader_node_types)} shader node types")

    for node_class in sorted(shader_node_types, key=lambda x: x.__name__):
        temp_tree.nodes.clear()

        try:
            node = temp_tree.nodes.new(type=node_class.__name__)

            node_info = {
                "bl_idname": node_class.__name__,
                "py_class_name": node_class.__name__,
                "name": node.bl_label,
                "label": node.label,
                "inputs": [],
                "outputs": [],
                "properties": [],
            }

            for inp in node.inputs:
                socket_info = {
                    "name": inp.name,
                    "type": inp.type,
                    "identifier": inp.identifier,
                    "default_value": get_socket_default_value(inp),
                }
                node_info["inputs"].append(socket_info)

            for out in node.outputs:
                socket_info = {
                    "name": out.name,
                    "type": out.type,
                    "identifier": out.identifier,
                }
                node_info["outputs"].append(socket_info)

            parent_props = set()
            for base in node_class.__bases__:
                if hasattr(base, "bl_rna"):
                    for prop in base.bl_rna.properties:
                        parent_props.add(prop.identifier)

            for prop in node.bl_rna.properties:
                if prop.identifier in parent_props:
                    continue
                if prop.identifier in ["rna_type", "dimensions", "internal_links"]:
                    continue

                try:
                    node_info["properties"].append(get_property_info(node, prop))
                except Exception as e:
                    print(
                        f"Could not get property {prop.identifier} for {node_class.__name__}: {e}"
                    )

            master_data["shader_nodes"][node_class.__name__] = node_info

        except Exception as e:
            print(f"Could not process {node_class.__name__}: {e}")

    bpy.data.materials.remove(temp_mat)

    if filepath:
        with open(filepath, "w") as f:
            json.dump(master_data, f, indent=4)
        print(f"Master shader nodes exported to {filepath}")
        print(f"Total nodes exported: {len(master_data['shader_nodes'])}")

    return master_data


if __name__ == "__main__":
    obj = bpy.context.active_object
    if obj and obj.active_material:
        mat_data = export_material_nodes_to_json(
            obj.active_material.name, f"/tmp/{obj.active_material.name}_nodes.json"
        )
        print(
            f"Exported {len(mat_data['nodes'])} nodes and {len(mat_data['links'])} links"
        )

    master_data = generate_master_shader_nodes_json(
        "/tmp/blender_shader_nodes_master.json"
    )

    print("\nExport Complete")
    print(f"Master file contains {len(master_data['shader_nodes'])} shader node types")


def export_all_materials(directory="/tmp/materials"):
    import os

    os.makedirs(directory, exist_ok=True)

    exported = 0
    for mat in bpy.data.materials:
        if mat.use_nodes:
            filepath = os.path.join(directory, f"{mat.name}.json")
            export_material_nodes_to_json(mat.name, filepath)
            exported += 1

    print(f"Exported {exported} materials to {directory}")


def export_selected_materials(directory="/tmp/materials"):
    import os

    os.makedirs(directory, exist_ok=True)

    materials = set()
    for obj in bpy.context.selected_objects:
        if hasattr(obj.data, "materials"):
            for mat in obj.data.materials:
                if mat and mat.use_nodes:
                    materials.add(mat)

    for mat in materials:
        filepath = os.path.join(directory, f"{mat.name}.json")
        export_material_nodes_to_json(mat.name, filepath)

    print(f"Exported {len(materials)} materials to {directory}")


generate_master_shader_nodes_json("C:/tmp/shader_nodes_master.json")