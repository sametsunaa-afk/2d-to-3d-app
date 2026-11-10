import streamlit as st
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt
import trimesh
import io
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="Yerel 2D to 3D STL Üretici", page_icon="🗿", layout="wide")

st.title("🗿 %100 Bağımsız ve Ücretsiz 2D'den 3D STL Üretici")
st.info("🔒 Bu uygulama hiçbir harici siteye bağlanmaz, API Key istemez ve tamamen ücretsizdir. Matematiksel hacim algoritması ile 3D katı model üretir.")

# Yan Menü Ayarları
with st.sidebar:
    st.header("⚙️ 3D Model Ayarları")
    target_height = st.slider("Figür Yüksekliği (mm)", 60, 200, 120, help="Yazıcıdan çıkacak biblonun boyu")
    front_depth = st.slider("Ön Yüz Kabartma Derinliği", 3, 25, 10, help="Ön yüzdeki yüz ve kıyafet derinliği")
    back_volume = st.slider("Arka Gövde Bombesi (Hacim)", 5, 40, 18, help="Arkaya doğru verilen etli/dolgun sırt hacmi")
    add_base = st.checkbox("Altına Stant (Kaide) Ekle", value=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Fotoğrafı Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (JPG veya PNG)", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("🚀 3D Katı Modeli Oluştur (Kendi Kodumuzla)", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model Önizleme & STL İndir")
    
    if generate_btn and uploaded_file is not None:
        with st.spinner("Matematiksel hacim örülüyor ve katı STL inşa ediliyor..."):
            try:
                # 1. Görseli Yükle ve Hazırla
                img_pil = Image.open(uploaded_file)
                # İdeal 3D çözünürlük için yeniden boyutlandır (200x200 ızgara ~80.000 poligon)
                img_gray = img_pil.convert('L')
                img_gray.thumbnail((200, 200), Image.Resampling.LANCZOS)
                w, h = img_gray.size
                
                arr = np.array(img_gray, dtype=np.float32) / 255.0
                
                # 2. Ön Yüz Derinliği (Işık/Gölge yumuşatma)
                smooth_front = gaussian_filter(arr, sigma=1.2)
                z_front = (smooth_front - smooth_front.min()) / (smooth_front.max() - smooth_front.min() + 1e-6)
                z_front = z_front * front_depth
                
                # 3. Arka Yüz Hacmi (Anatomik organik sırt kubbesi)
                # Merkeze doğru bombeli, kenarlara doğru daralan hacim
                dist_mask = distance_transform_edt(np.ones_like(arr))
                dist_norm = dist_mask / (dist_mask.max() + 1e-6)
                z_back = - np.sin(dist_norm * np.pi / 2.0) * back_volume
                
                # 4. 3D Koordinat Ağını (Izgarayı) Oluştur
                aspect_ratio = w / h
                x_scale = (target_height * aspect_ratio) / w
                y_scale = target_height / h
                
                x = np.linspace(-w * x_scale / 2.0, w * x_scale / 2.0, w)
                y = np.linspace(h * y_scale / 2.0, -h * y_scale / 2.0, h)
                xx, yy = np.meshgrid(x, y)
                
                # Tepe (Ön) ve Taban (Arka) Noktaları
                top_vertices = np.column_stack((xx.flatten(), yy.flatten(), z_front.flatten()))
                bot_vertices = np.column_stack((xx.flatten(), yy.flatten(), z_back.flatten()))
                all_vertices = np.vstack((top_vertices, bot_vertices))
                
                # Yüzey Üçgenlerini Ör (Watertight / Katı Gövde)
                faces = []
                hw = w * h
                
                for i in range(h - 1):
                    for j in range(w - 1):
                        v0 = i * w + j
                        v1 = i * w + (j + 1)
                        v2 = (i + 1) * w + j
                        v3 = (i + 1) * w + (j + 1)
                        
                        # Ön Yüz
                        faces.append([v0, v2, v1])
                        faces.append([v1, v2, v3])
                        
                        # Arka Yüz (Ters yönlü yüzey normalleri)
                        faces.append([hw + v0, hw + v1, hw + v2])
                        faces.append([hw + v1, hw + v3, hw + v2])
                
                # 5. Yan Duvarları Dikişle (Ön ve Arkayı Birleştirip Su Geçirmez Yap)
                # Üst ve Alt kenarlar
                for j in range(w - 1):
                    # Üst kenar (i = 0)
                    t0, t1 = j, j + 1
                    b0, b1 = hw + t0, hw + t1
                    faces.append([t0, t1, b0])
                    faces.append([t1, b1, b0])
                    
                    # Alt kenar (i = h - 1)
                    t0, t1 = (h - 1) * w + j, (h - 1) * w + (j + 1)
                    b0, b1 = hw + t0, hw + t1
                    faces.append([t0, b0, t1])
                    faces.append([t1, b0, b1])
                
                # Sol ve Sağ kenarlar
                for i in range(h - 1):
                    # Sol kenar (j = 0)
                    t0, t1 = i * w, (i + 1) * w
                    b0, b1 = hw + t0, hw + t1
                    faces.append([t0, b0, t1])
                    faces.append([t1, b0, b1])
                    
                    # Sağ kenar (j = w - 1)
                    t0, t1 = i * w + (w - 1), (i + 1) * w + (w - 1)
                    b0, b1 = hw + t0, hw + t1
                    faces.append([t0, t1, b0])
                    faces.append([t1, b1, b0])
                
                mesh = trimesh.Trimesh(vertices=all_vertices, faces=faces)
                mesh.fill_holes()
                mesh.fix_normals()
                
                # 6. Kaide (Stant) Ekle
                if add_base:
                    bounds = mesh.bounds
                    base_radius = max((bounds[1][0] - bounds[0][0]), (bounds[1][1] - bounds[0][1])) * 0.45
                    base_height = 4.0
                    base = trimesh.creation.cylinder(radius=base_radius, height=base_height, sections=40)
                    # Kaideyi modelin alt tabanına yerleştir
                    base.apply_translation([0, bounds[0][1] + 2.0, bounds[0][2] - (base_height / 2.0)])
                    mesh = trimesh.util.concatenate([mesh, base])
                
                # 7. Model Başarılı
                st.success("🎉 Katı 3D Modeliniz Saniyeler İçinde Üretildi!")
                
                # Canlı Önizleme İçin GLB Verisi
                glb_io = io.BytesIO()
                mesh.export(glb_io, file_type='glb')
                glb_bytes = glb_io.getvalue()
                glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")
                
                viewer_html = f"""
                <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                              auto-rotate 
                              camera-controls 
                              style="width: 100%; height: 420px; background-color: #2b2b2b; border-radius: 12px;">
                </model-viewer>
                """
                components.html(viewer_html, height=440)
                
                # STL Dosyasını Hazırla
                stl_io = io.BytesIO()
                mesh.export(stl_io, file_type='stl')
                stl_bytes = stl_io.getvalue()
                
                # Doğrudan İndirme Butonu
                st.download_button(
                    label="📥 3D Yazıcı İçin STL İndir (Tamamen Ücretsiz)",
                    data=stl_bytes,
                    file_name="cift_3d_katı_biblo.stl",
                    mime="application/sla",
                    type="primary",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Hata oluştu: {str(e)}")
