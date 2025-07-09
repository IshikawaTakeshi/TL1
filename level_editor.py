import bpy
import os
import math
import mathutils
import bpy_extras
import gpu
import gpu_extras.batch
import copy
import json
from bpy_extras.io_utils import ImportHelper


# ブレンダーに登録するアドオン情報
bl_info = {
    "name": "レベルエディタ",
    "author": "TAKESHI_ISHIKAWA",
    "version": (1, 0),
    "blender": (3, 3, 1),
    "location": "",
    "description": "レベルエディタ",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"
}

#///////////////////////////////////////////////////////////////////////////////////
# オペレータ シーン読み込み
#///////////////////////////////////////////////////////////////////////////////////

class MYADDON_OT_import_scene(bpy.types.Operator,bpy_extras.io_utils.ExportHelper):
    bl_idname = "myaddon.myaddon_ot_import_scene"
    bl_label = "シーン読み込み"
    bl_description = "シーン情報をImportします"
    #入力するファイルの拡張子
    filename_ext = ".json"

    #==============================================================================
    # 実行関数
    #==============================================================================
    def execute(self,context):

        print("シーン情報をImportします")
        self.import_json()
        print("シーン情報をImportしました")
        self.report({'INFO'},"シーン情報をImportしました")
        return {'FINISHED'}
    
    #==============================================================================
    # ファイル読み込み
    #==============================================================================
    def import_json(self):
        #ファイル読み込み
        with open(self.filepath,"rt",encoding="utf-8") as f:
            data = json.load(f)

        #オブジェクト生成
        if "objects" in data:
            for obj_data in data["objects"]:
                self.create_object_recursive(obj_data, parent=None)
    
    #==============================================================================
    # ファイル読み込み
    #==============================================================================
    def create_object_recursive(self,obj_data,parent):

        name = obj_data.get("name", "ImportedObject")
        obj_type = obj_data.get("type", "EMPTY")
        file_name = obj_data.get("file_name", None)
        obj = None

         # === resource_dir 取得 ===
        ADDON_NAME = "level_editor"
        addon_prefs = bpy.context.preferences.addons[ADDON_NAME].preferences
        resource_dir = addon_prefs.resource_dir if hasattr(addon_prefs, "resource_dir") else ""

        # === file_nameのパス解決 ===
        abs_file_path = file_name
        if file_name and not os.path.isabs(file_name) and resource_dir:
            abs_file_path = os.path.join(resource_dir, file_name)

        if obj_type == "MESH" and file_name is not None:
            ext = os.path.splitext(abs_file_path)[1].lower()

            if ext == ".obj" and os.path.exists(abs_file_path):
                bpy.ops.import_scene.obj(filepath=abs_file_path)
                imported_objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
                if imported_objs:
                    obj = imported_objs[0]
            elif ext in [".gltf", ".glb"] and os.path.exists(abs_file_path):
                bpy.ops.import_scene.gltf(filepath=abs_file_path)
                imported_objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
                if imported_objs:
                    obj = imported_objs[0]

            if obj:
                obj.name = name
            else:
                bpy.ops.object.add(type='EMPTY')
                obj = bpy.context.active_object
                obj.name = name

        elif obj_type == "CAMERA":
            bpy.ops.object.camera_add()
            obj = bpy.context.active_object
            obj.name = name
        elif obj_type == "LIGHT":
            bpy.ops.object.light_add(type='POINT')
            obj = bpy.context.active_object
            obj.name = name
        else:
            bpy.ops.object.add(type='EMPTY')
            obj = bpy.context.active_object
            obj.name = name

        #SRT
        transform = obj_data.get("transform",{})
        translate = transform.get("translation",)
        rotate   = transform.get("rotation", )
        scale = transform.get("scaling",) 
        obj.location = translate
        obj.rotation_euler = [math.radians(r) for r in rotate]
        obj.scale = scale
        
        #カスタムプロパティ
        if "file_name" in obj_data:
            obj["file_name"] = obj_data["file_name"]

        #コライダー情報
        if "collider" in obj_data:
            collider = obj_data["collider"]
            obj["collider"] = collider.get("type","")
            obj["collider_center"] = mathutils.Vector(collider["center"])
            if "size" in collider:
                obj["collider_size"] = mathutils.Vector(collider["size"])
            elif "radius" in collider:
                obj["collider_radius"] = collider["radius"]

        #親子関係
        if parent is not None:
            obj.parent = parent
        #子オブジェクト
        for child_data in obj_data.get("children",[]):
            self.create_object_recursive(child_data,parent=obj)



    

#///////////////////////////////////////////////////////////////////////////////////
# オペレータ シーン出力
#///////////////////////////////////////////////////////////////////////////////////
class MYADDON_OT_export_scene(bpy.types.Operator,bpy_extras.io_utils.ExportHelper):
    bl_idname = "myaddon.myaddon_ot_export_scene"
    bl_label = "シーン出力"
    bl_description = "シーン情報をExprotします"
    #出力するファイルの拡張子
    filename_ext = ".json"


    #==============================================================================
    # 実行関数
    #==============================================================================
    def execute(self,context):


        print("シーン情報をExprotします")


        self.export_json()
       
        print("シーン情報をExprotしました")
        self.report({'INFO'},"シーン情報をExprotしました")


        return {'FINISHED'}
   
    #==============================================================================
    # ファイルに出力
    #==============================================================================
    def export(self):


        print("シーン情報出力開始...%r" % self.filepath)


        #ファイルをテキスト形式で書き出し用にオープン
        #スコープを抜けると自動的にクローズされる
        with open(self.filepath,"wt") as file:


            #ファイルに文字列を書き込む
            self.write_and_print(file,"SCENE")


             #シーン内すべてのオブジェクトについて
            for object in bpy.context.scene.objects:
               
                #親オブジェクトの名前表示
                if object.parent:
                    continue
               
                #シーン直下のオブジェクトをルートノード(深さ0)とし、再帰関数で走査
                self.parse_scene_recursive(file,object,0)

    #=============================================================================
    # Json形式でファイル出力
    #=============================================================================
    def export_json(self):
        """Json形式でファイル出力"""
        #保存情報をまとめるdict
        json_object_root = dict()
        #ノード名
        json_object_root["name"] = "scene"
        #オブジェクトリストを作成
        json_object_root["objects"] = list()
        #シーン内の全オブジェクト走査してパック
        for object in bpy.context.scene.objects:
            #親オブジェクトがあるものはスキップ(代わりに親から呼び出す)
            if object.parent:
                continue
            
            #シーン直下のオブジェクトルートノードとし、再帰関数で走査
            self.parse_scene_recursive_json(json_object_root["objects"],object,0)
     
        #オブジェクトをJSON文字列にエンコード
        json_text = json.dumps(json_object_root,ensure_ascii=False,cls=json.JSONEncoder,indent=4)
        #コンソールに出力してみる
        print(json_text)
        #ファイルをテキスト形式で書き出し用にオープン
        #スコープを抜けると自動的にクローズされる
        with open(self.filepath,"wt",encoding="utf-8") as file:
            #ファイルに文字列を書き込む
            file.write(json_text)
    
    #==============================================================================
    # シーン解析用再帰関数
    #==============================================================================
    def parse_scene_recursive(self,file,object,level):
        #深さ分インデントする(タブを挿入)
        indent = ''
        for i in range(level):
            indent += "\t"


        #オブジェクト名書き込み
        self.write_and_print(file,indent + object.type)
        trans,rot,scale = object.matrix_local.decompose()
        #回転をQuaternionからEulerに変換
        rot = rot.to_euler()
        #ラジアンから度数法に変換
        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)
        #トランスフォーム情報を表示
        self.write_and_print(file,indent + "T(%f,%f,%f)" % (trans.x,trans.y,trans.z))
        self.write_and_print(file,indent + "R(%f,%f,%f)" % (rot.x,rot.y,rot.z))
        self.write_and_print(file,indent + "S(%f,%f,%f)" % (scale.x,scale.y,scale.z))
        #========== カスタムプロパティ'file_name' ==========#
        if "file_name" in object:
            self.write_and_print(file, indent + "N %s" % object["file_name"])
        #========== カスタムプロパティ'collision' ==========#
        if "collider" in object:
            self.write_and_print(file,indent + "C %s" % object["collider"])
            #collider_center
            temp_str = indent + "CC %f %f %f"
            temp_str %= (object["collider_center"][0],object["collider_center"][1],object["collider_center"][2])
            self.write_and_print(file,temp_str)
            #collider_size
            temp_str = indent + "CS %f %f %f"
            temp_str %= (object["collider_size"][0],object["collider_size"][1],object["collider_size"][2])
            self.write_and_print(file,temp_str)


        self.write_and_print(file, indent + 'END')
        self.write_and_print(file,'')


        #子ノードへ進む(深さが1上がる)
        for child in object.children:
            self.parse_scene_recursive(file,child,level + 1)


   
    def write_and_print(self,file,str):
        print(str)


        file.write(str)
        file.write('\n')


    def parse_scene_recursive_json(self,data_parent,object,level):
        #シーンのオブジェクト1個分のjsonオブジェクト生成
        json_object = dict()
        #オブジェクト種類
        json_object["type"] = object.type
        #オブジェクト名
        json_object["name"] = object.name
        #Aその他情報をパック
        trans,rot,scale = object.matrix_local.decompose()
         #回転をQuaternionからEulerに変換
        rot = rot.to_euler()
        #ラジアンから度数法に変換
        rot.x = math.degrees(rot.x)
        rot.y = math.degrees(rot.y)
        rot.z = math.degrees(rot.z)
        #トランスフォーム情報をディクショナリに登録
        transform = dict()
        transform["translation"] = (trans.x,trans.y,trans.z)
        transform["rotation"] = (rot.x,rot.y,rot.z)
        transform["scaling"] = (scale.x,scale.y,scale.z)
        #まとめて一個分のjsonオブジェクトに登録
        json_object["transform"] = transform

        #カスタムプロパティ'file_name'
        if "file_name" in object:
            json_object["file_name"] = object["file_name"]
        
        #カスタムプロパティ'collider'
        if "collider" in object:
            collider = dict()
            collider["type"] = object["collider"]
            collider["center"] = (
                object["collider_center"].to_list()
                if hasattr(object["collider_center"], "to_list")
                else list(object["collider_center"])
            )
            if object["collider"] == "BOX":
                collider["size"]  = (
                    object["collider_size"].to_list()
                    if hasattr(object["collider_size"], "to_list")
                    else list(object["collider_size"])
                )
            elif object["collider"] == "SPHERE":
                collider["radius"] = object["collider_radius"] if "collider_radius" in object else 1.0
            json_object["collider"] = collider

        #1個分のjsonオブジェクトを親オブジェクトに登録
        data_parent.append(json_object)
        #B直接の子供リストを走査
        if len(object.children) > 0:
            json_object["children"] = list()
        #子ノードへ進む
        for child in object.children:
            self.parse_scene_recursive_json(json_object["children"],child,level + 1)
 
#///////////////////////////////////////////////////////////////////////////////////
# 頂点を伸ばす
#///////////////////////////////////////////////////////////////////////////////////
class MYADDON_OT_strecth_vertex(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_strecth_vertx"
    bl_label = "頂点を伸ばす"
    bl_description = "頂点座標を引っ張って伸ばします"
    #リドゥ、アンドゥ可能オプション
    bl_options = {'REGISTER','UNDO'}
     
    #メニューを実行した時に呼ばれるコールバック関数
    def execute(self,context):
        bpy.data.objects["Cube"].data.vertices[0].co.x += 1.0
        print("頂点を伸ばしました")


        #オペレーターの命令終了を通知
        return {'FINISHED'}


#///////////////////////////////////////////////////////////////////////////////////
# ICO球生成
#///////////////////////////////////////////////////////////////////////////////////
class MYADDON_OT_create_ico_sphere(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_create_object"
    bl_label = "ICO球生成"
    bl_description = "ICO球を生成します"
    bl_options = {'REGISTER', 'UNDO'}


    # メニューを実行したときに呼ばれる関数
    def execute(self, context):
        bpy.ops.mesh.primitive_ico_sphere_add()
        print("ICO球を生成しました。")


        return {'FINISHED'}
   
#///////////////////////////////////////////////////////////////////////////////////
# filename追加
#///////////////////////////////////////////////////////////////////////////////////
class MYADDON_OT_add_filename(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_filename"
    bl_label = "FileName追加"
    bl_description = "['file_name']カスタムプロパティを追加します"
    bl_options = {"REGISTER","UNDO"}

    def execute(self,context):
        #['file_name']カスタムプロパティの追加
        context.object["file_name"] = ""
        return {"FINISHED"}


#///////////////////////////////////////////////////////////////////////////////////
# collider追加
#///////////////////////////////////////////////////////////////////////////////////
class MYADDON_OT_add_collider(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_add_collider"
    bl_label = "コライダー追加"
    bl_description = "['collider']カスタムプロパティを追加します"
    bl_options = {"REGISTER","UNDO"}

    collider_type: bpy.props.EnumProperty(
        name="Collider Type",
        description="コライダーの種類を選択",
        items=[
            ('BOX','Box','BOXCollider'),
            ('SPHERE','Sphere','SPHERECollider'),
        ],
        default='BOX'
    )
  
    def execute(self,context):

        obj = context.object
        if self.collider_type == 'BOX':
            #['collider']カスタムプロパティ追加
            obj["collider"] = "BOX"
            obj["collider_center"] = mathutils.Vector((0,0,0))
            obj["collider_size"] = mathutils.Vector((1,1,1))
        elif self.collider_type == 'SPHERE':
            obj["collider"] = "SPHERE"
            obj["collider_center"] = mathutils.Vector((0,0,0))
            obj["collider_radius"] = 0.5
        return {"FINISHED"}
    
    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self)
    
#///////////////////////////////////////////////////////////////////////////////////
# collider削除
#///////////////////////////////////////////////////////////////////////////////////

class MYADDON_OT_remove_collider(bpy.types.Operator):
    bl_idname = "myaddon.myaddon_ot_remove_collider"
    bl_label = "コライダー削除"
    bl_description = "コライダーのカスタムプロパティを削除します"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.object
        for key in ["collider", "collider_center", "collider_size", "collider_radius"]:
            if key in obj:
                del obj[key]
        return {'FINISHED'}
    
#///////////////////////////////////////////////////////////////////////////////////
# FileNameの一括変更
#///////////////////////////////////////////////////////////////////////////////////   
class MYADDON_OT_batch_set_filename(bpy.types.Operator):
    bl_idname = "myaddon.batch_set_filename"
    bl_label = "FileName一括設定"
    bl_description = "選択オブジェクトのFileNameカスタムプロパティを一括で設定します"
    bl_options = {'REGISTER', 'UNDO'}

    filename: bpy.props.StringProperty(
        name="file_name",
        description="設定するFileName（全選択オブジェクトに同じ値が入ります）"
    )

    def execute(self, context):
        for obj in context.selected_objects:
            obj["file_name"] = self.filename
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
#///////////////////////////////////////////////////////////////////////////////////
# Colliderの一括変更
#///////////////////////////////////////////////////////////////////////////////////  
    
class MYADDON_OT_batch_add_collider(bpy.types.Operator):
    bl_idname = "myaddon.batch_add_collider"
    bl_label = "コライダー一括追加・設定"
    bl_description = "選択オブジェクトにコライダーをまとめて追加/設定します"
    bl_options = {'REGISTER', 'UNDO'}

    collider_type: bpy.props.EnumProperty(
        name="Collider Type",
        description="コライダーの種類",
        items=[
            ('BOX','Box','BOX Collider'),
            ('SPHERE','Sphere','Sphere Collider'),
        ],
        default='BOX'
    )
    collider_size: bpy.props.FloatVectorProperty(
        name="Boxサイズ",
        subtype='XYZ',
        default=(1.0, 1.0, 1.0),
        size=3
    )
    collider_radius: bpy.props.FloatProperty(
        name="Sphere半径",
        default=0.5
    )
    collider_center: bpy.props.FloatVectorProperty(
        name="中心オフセット",
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        size=3
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "collider_type")
        if self.collider_type == 'BOX':
            layout.prop(self, "collider_size")
        elif self.collider_type == 'SPHERE':
            layout.prop(self, "collider_radius")
        layout.prop(self, "collider_center")

    def execute(self, context):
        for obj in context.selected_objects:
            if self.collider_type == 'BOX':
                obj["collider"] = "BOX"
                obj["collider_center"] = mathutils.Vector(self.collider_center)
                obj["collider_size"] = mathutils.Vector(self.collider_size)
                # SPHEREプロパティがあれば消す
                if "collider_radius" in obj:
                    del obj["collider_radius"]
            elif self.collider_type == 'SPHERE':
                obj["collider"] = "SPHERE"
                obj["collider_center"] = mathutils.Vector(self.collider_center)
                obj["collider_radius"] = self.collider_radius
                # BOXプロパティがあれば消す
                if "collider_size" in obj:
                    del obj["collider_size"]
            # 他の不要なカスタムプロパティがあればここで整理可
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


#///////////////////////////////////////////////////////////////////////////////////
# トップバーの拡張メニュー
#///////////////////////////////////////////////////////////////////////////////////
class TOPBAR_MT_my_menu(bpy.types.Menu):
    #Blenderがクラスを識別するための固有の文字列
    bl_idname = "TOPBAR_MT_my_menu"
    #メニューのラベルとして表示される文字列
    bl_label = "MyMenu"
    #著者表示用の文字列
    bl_description = "拡張メニュー by " + bl_info["author"]


    #サブメニューの描画
    def draw(self,context):


        #トップバーの「エディターメニュー」に項目（オペレータ）を追加
        #頂点を伸ばす
        self.layout.operator(MYADDON_OT_strecth_vertex.bl_idname,
             text=MYADDON_OT_strecth_vertex.bl_label)

        #ICO球生成
        self.layout.operator(MYADDON_OT_create_ico_sphere.bl_idname,
             text=MYADDON_OT_create_ico_sphere.bl_label)
        
        #シーンのインポート
        self.layout.operator(MYADDON_OT_import_scene.bl_idname,
             text=MYADDON_OT_import_scene.bl_label)

        #シーンのエクスポート
        self.layout.operator(MYADDON_OT_export_scene.bl_idname,
             text=MYADDON_OT_export_scene.bl_label)
        
        self.layout.operator(MYADDON_OT_batch_set_filename.bl_idname,
             text=MYADDON_OT_batch_set_filename.bl_label)
        
        self.layout.operator(MYADDON_OT_batch_add_collider.bl_idname,
             text=MYADDON_OT_batch_add_collider.bl_label)

    #既存のメニューにサブメニューを追加
    def submenu(self,context):


        # ID指定でサブメニューを追加
        self.layout.menu(TOPBAR_MT_my_menu.bl_idname)


#///////////////////////////////////////////////////////////////////////////////////
# オブジェクトのファイルネームパネル
#///////////////////////////////////////////////////////////////////////////////////
class OBJECT_PT_file_name(bpy.types.Panel):
    bl_idname      = "OBJECT_PT_file_name"
    bl_label       = "FileName"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "object"


    #サブメニュー描画
    def draw(self,context):


        #パネルに項目を追加
        if "file_name" in context.object:
            #既にプロパティがあれば、プロパティを表示
            self.layout.prop(context.object, '["file_name"]',text=self.bl_label)
        else:
            #プロパティがなければ、プロパティ追加ボタンを表示
            self.layout.operator(MYADDON_OT_add_filename.bl_idname)
       
#///////////////////////////////////////////////////////////////////////////////////
#パネル　collider
#///////////////////////////////////////////////////////////////////////////////////
class OBJECT_PT_collider(bpy.types.Panel):
    bl_idname      = "OBJECT_PT_collider"
    bl_label       = "Collider"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "object"


    #サブメニュー描画
    def draw(self,context):

        obj = context.object
        if "collider" in obj:

            collider_type = obj["collider"]

            #既にプロパティがあれば、プロパティを表示
            self.layout.label(text=f"Type: {obj['collider']}")
            self.layout.prop(obj, '["collider_center"]',text="Center")

            if collider_type == "BOX":
                self.layout.prop(obj, '["collider_size"]',text="Size")
            elif collider_type == "SPHERE":
                self.layout.prop(obj, '["collider_radius"]',text="Radius")

            #削除ボタン
            self.layout.operator("myaddon.myaddon_ot_remove_collider",text="コライダー削除",icon='X')
        else:
            self.layout.operator("myaddon.myaddon_ot_add_collider", text="コライダー追加", icon='PLUS')




#///////////////////////////////////////////////////////////////////////////////////
# コライダー描画
#///////////////////////////////////////////////////////////////////////////////////
class DrawCollider:

    #描画ハンドル
    handle = None

    #3Dビューに登録する描画関数
    @staticmethod
    def draw_collider():
        import mathutils
        import math
        import copy
        import gpu
        import gpu_extras

        #頂点データ
        vertices = {"pos":[]}
        #インデックスデータ
        indices = []
        #球の分割数
        SEGMENTS = 32

        #現在シーンのオブジェクトリストを走査
        for obj in bpy.context.scene.objects:
            #コライダープロパティがなければ、描画をスキップ
            if "collider" not in obj:
                continue

            collider_type = obj["collider"]

            if collider_type == "BOX":
                # 中心点、サイズの変数を宣言
                # 必ずワールド実寸値で格納・取得すること
                center = mathutils.Vector(obj["collider_center"])
                size   = mathutils.Vector(obj["collider_size"])

                # 各頂点の、オブジェクト中心からのオフセット
                offsets = [
                    [-1.0,-1.0,-1.0],[+1.0,-1.0,-1.0],
                    [-1.0,+1.0,-1.0],[+1.0,+1.0,-1.0],
                    [-1.0,-1.0,+1.0],[+1.0,-1.0,+1.0],
                    [-1.0,+1.0,+1.0],[+1.0,+1.0,+1.0],
                ]

                # 現在の頂点数を取得
                start = len(vertices["pos"])

                # Boxの8頂点分for文を回す
                for offset in offsets:
                    # サイズをワールド空間に合わせる（collider_sizeは必ずワールド実寸）
                    pos = center + mathutils.Vector((
                        offset[0]*size[0],
                        offset[1]*size[1],
                        offset[2]*size[2]
                    ))
                    # ローカル→ワールド変換
                    pos = obj.matrix_world @ pos
                    vertices['pos'].append(pos)

                # 辺を構成するインデックス（12本）
                # 前面
                indices += [
                    [start+0, start+1], [start+1, start+3], [start+3, start+2], [start+2, start+0],
                    # 奥面
                    [start+4, start+5], [start+5, start+7], [start+7, start+6], [start+6, start+4],
                    # 前後をつなぐ
                    [start+0, start+4], [start+1, start+5], [start+2, start+6], [start+3, start+7]
                ]

            elif collider_type == "SPHERE":
                center = mathutils.Vector(obj["collider_center"])
                radius = float(obj.get("collider_radius", 1.0))  # 必ずfloatで取得
                start = len(vertices["pos"])
                # xy平面
                xy_indices = []
                for i in range(SEGMENTS):
                    theta0 = 2*math.pi*i/SEGMENTS
                    p = center + mathutils.Vector((
                        math.cos(theta0)*radius,
                        math.sin(theta0)*radius,
                        0
                    ))
                    p = obj.matrix_world @ p
                    vertices['pos'].append(p)
                    xy_indices.append(len(vertices['pos'])-1)
                for i in range(SEGMENTS):
                    indices.append([xy_indices[i], xy_indices[(i+1)%SEGMENTS]])
                # xz平面
                xz_indices = []
                for i in range(SEGMENTS):
                    theta0 = 2*math.pi*i/SEGMENTS
                    p = center + mathutils.Vector((
                        math.cos(theta0)*radius,
                        0,
                        math.sin(theta0)*radius
                    ))
                    p = obj.matrix_world @ p
                    vertices['pos'].append(p)
                    xz_indices.append(len(vertices['pos'])-1)
                for i in range(SEGMENTS):
                    indices.append([xz_indices[i], xz_indices[(i+1)%SEGMENTS]])
                # yz平面
                yz_indices = []
                for i in range(SEGMENTS):
                    theta0 = 2*math.pi*i/SEGMENTS
                    p = center + mathutils.Vector((
                        0,
                        math.cos(theta0)*radius,
                        math.sin(theta0)*radius
                    ))
                    p = obj.matrix_world @ p
                    vertices['pos'].append(p)
                    yz_indices.append(len(vertices['pos'])-1)
                for i in range(SEGMENTS):
                    indices.append([yz_indices[i], yz_indices[(i+1)%SEGMENTS]])

        if len(vertices["pos"]) == 0:
            return

        #ビルトインのシェーダを取得
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        #バッチを作成(引数：シェーダ、トポロジー、頂点データ、インデックスデータ)
        batch = gpu_extras.batch.batch_for_shader(shader, "LINES", vertices, indices=indices)
        #シェーダのパラメータ設定
        color = [0.5, 1.0, 1.0, 1.0]
        shader.bind()
        shader.uniform_float("color", color)
        #描画
        batch.draw(shader)

class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    resource_dir: bpy.props.StringProperty(
        name="リソースフォルダ",
        subtype='DIR_PATH',
        default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "resource_dir")

#///////////////////////////////////////////////////////////////////////////////////
# Blenderに登録するクラスリスト
#///////////////////////////////////////////////////////////////////////////////////
classes = (
    MYADDON_OT_strecth_vertex,
    MYADDON_OT_create_ico_sphere,
    MYADDON_OT_import_scene,
    MYADDON_OT_export_scene,
    MYADDON_OT_add_filename,
    MYADDON_OT_add_collider,
    MYADDON_OT_remove_collider,
    MYADDON_OT_batch_add_collider,
    MYADDON_OT_batch_set_filename,
    MyAddonPreferences,
    TOPBAR_MT_my_menu,
    OBJECT_PT_file_name,
    OBJECT_PT_collider,
)


#===================================================================================
# アドオン有効化時コールバック
#===================================================================================
def register():


    #Blenderにクラスを登録
    for cls in classes:
        bpy.utils.register_class(cls)


    #メニューに項目を追加
    bpy.types.TOPBAR_MT_editor_menus.append(TOPBAR_MT_my_menu.submenu)
    #3Dビューに描画関数を追加
    DrawCollider.handle = bpy.types.SpaceView3D.draw_handler_add(DrawCollider.draw_collider,(),"WINDOW","POST_VIEW")
    print("レベルエディタが有効化されました。")


#===================================================================================
# アドオン無効化時コールバック
#===================================================================================
def unregister():
    #メニューから項目を削除
    bpy.types.TOPBAR_MT_editor_menus.remove(TOPBAR_MT_my_menu.submenu)
    #3dビューからクラスを削除
    bpy.types.SpaceView3D.draw_handler_remove(DrawCollider.handle,"WINDOW")


    #Blenderからクラスを削除
    for cls in classes:
        bpy.utils.unregister_class(cls)
    print("レベルエディタが無効化されました。")


#===================================================================================
# メニュー項目描画
#===================================================================================
def draw_menu_manual(self,context):
   
    self.layout.operator("wm.url_open_preset", text="Manual", icon="HELP")
   
#///////////////////////////////////////////////////////////////////////////////////
#main code
#///////////////////////////////////////////////////////////////////////////////////
if __name__ == "__main__":
    register()

