import streamlit as st
import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, distance_transform_edt, laplace
from collections import Counter
import trimesh
import io
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="Saf Silüet 3D Biblo Üretici - Yüksek Kalite", page_icon="🗿", layout="wide")

st.title("🗿 Yüksek Kaliteli 3D Silüet & Yüz Hatlı Biblo Üretici")
st.markdown("Arka plandaki tüm çerçeve atılır; **yüksek çözünürlüklü detay çıkarma** ile yüz hatları netleştirilmiş 3D heykelcik üretilir.")

# Yan Menü Kontrolleri
with st.sidebar:
    st.header("🎛️ Biblo Ayarları")
    target_height = st.slider("Figür Boyu (mm)", 60, 200, 120, help="Yazıcıdan çıkacak figürün boyu")
    body_thickness = st.slider("Figür Kalınlığı / Hacmi", 4, 30, 14, help="Kişilerin ön ve arka vücut dolgunluğu")
    
    st.divider()
    st.header("🔍 Detay & Kalite Ayarları")
    mesh_res = st.select_slider(
        "Model Çözünürlüğü (Mesh Kalitesi)",
        options=[250, 400, 600, 800],
        value=500 if 500 in [250, 400, 600, 800] else 400,
        help="Yüksek değerler yüz hatlarını son derece netleştirir ancak işlem süresini artırır."
    )
    detail_strength = st.slider("Yüz & Kıyafet Detay Keskinliği", 1, 30, 15, help="Yüz hatlarının belirginliğini artırır")
    smoothness = st.slider("Yüzey Pürüzsüzlüğü", 0.5, 5.0, 1.2, step=0.1, help="Gürültüyü azaltır. Düşük değer detayları daha net tutar.")
    
    st.divider()
    add_base = st.checkbox("Ayakların Altına Yuvarlak Kaide Ekle", value=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Saydam PNG Görselini Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (Arka plansız PNG)", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("✂️ Yüksek Kalite 3D Figürü Üret", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model Önizleme & Dosya İndir")
    
    if generate_btn and uploaded_file is not None:
        with st.spinner("Yüksek çözünürlüklü yüz hatları işleniyor ve 3D örülüyor..."):
            try:
                # 1. Görseli Yükle ve Kullanıcının Seçtiği Çözünürlüğe Ölçekle
                img_pil = Image.open(uploaded_file)
                img_pil.thumbnail((mesh_res, mesh_res), Image.Resampling.LANCZOS)
                w, h = img_pil.size
                
                # Saydamlık Maskesi
                if img_pil.mode == 'RGBA':
                    alpha = np.array(img_pil.split()[-1], dtype=np.float32) / 255.0
                    mask = (alpha > 0.15)
                else:
                    gray_temp = np.array(img_pil.convert('L'), dtype=np.float32)
                    mask = (gray_temp > 20)

                if np.sum(mask) == 0:
                    st.error("Görselde kişi alanı tespit edilemedi! Lütfen arka planı saydam bir PNG yükleyin.")
                else:
                    # 2. Yüz ve Detay Çıkarma Algoritması (Geliştirilmiş)
                    img_gray = img_pil.convert('L')
                    
                    # Kontrastı artırarak yüzdeki gölge ve hatları belirginleştir
                    img_eq = ImageOps.equalize(img_gray)
                    arr = np.array(img_eq, dtype=np.float32) / 255.0

                    # Keskinlik ve Detay Haritası (Laplacian + High Pass Filtresi)
                    blurred = gaussian_filter(arr, sigma=float(smoothness))
                    high_pass = arr - blurred
                    lap = laplace(arr)
                    
                    # Detay bileşimi
                    combined_detail = (high_pass * 0.7) - (lap * 0.3)
                    z_details = combined_detail * float(detail_strength)

                    # 3. Vücut Hacmi (Distance Transform)
                    dist = distance_transform_edt(mask)
                    dist_norm = dist / (dist.max() + 1e-6)
                    
                    # Ön Z koordinatı: Vücut bombesi + Detay kabarık hatları
                    z_front = (np.sin(dist_norm * np.pi / 2.0) * float(body_thickness)) + z_details + 1.0
                    # Arka Z koordinatı: Düzgün sırt
                    z_back = - (np.sin(dist_norm * np.pi / 2.0) * float(body_thickness) * 0.85) - 1.0

                    # 4. Koordinat Ölçekleme
                    aspect_ratio = w / h
                    x_scale = (target_height * aspect_ratio) / w
                    y_scale = target_height / h
                    
                    x = np.linspace(-w * x_scale / 2.0, w * x_scale / 2.0, w)
                    y = np.linspace(h * y_scale / 2.0, -h * y_scale / 2.0, h)
                    xx, yy = np.meshgrid(x, y)

                    # 5. Vertex (Nokta) Haritası Oluşturma
                    vertex_map = np.full((h, w), -1, dtype=np.int32)
                    top_verts = []
                    bot_verts = []
                    curr_idx = 0

                    for i in range(h):
                        for j in range(w):
                            if mask[i, j]:
                                vertex_map[i, j] = curr_idx
                                top_verts.append([xx[i, j], yy[i, j], z_front[i, j]])
                                bot_verts.append([xx[i, j], yy[i, j], z_back[i, j]])
                                curr_idx += 1

                    num_verts = curr_idx
                    all_vertices = np.vstack([np.array(top_verts), np.array(bot_verts)])

                    # 6. Yüzey Üçgenleme (Triangulation)
                    faces_front = []
                    faces_back = []

                    for i in range(h - 1):
                        for j in range(w - 1):
                            v0 = vertex_map[i, j]
                            v1 = vertex_map[i, j + 1]
                            v2 = vertex_map[i + 1, j]
                            v3 = vertex_map[i + 1, j + 1]

                            if v0 != -1 and v1 != -1 and v2 != -1 and v3 != -1:
                                faces_front.append([v0, v2, v1])
                                faces_front.append([v1, v2, v3])
                                faces_back.append([num_verts + v0, num_verts + v1, num_verts + v2])
                                faces_back.append([num_verts + v1, num_verts + v3, num_verts + v2])

                    # 7. Dış Silüet Kenar Duvarları Örme
                    edge_counts = Counter()
                    for f in faces_front:
                        edge_counts[(f[0], f[1])] += 1
                        edge_counts[(f[1], f[2])] += 1
                        edge_counts[(f[2], f[0])] += 1

                    boundary_edges = [edge for edge, count in edge_counts.items() if (edge[1], edge[0]) not in edge_counts]

                    wall_faces = []
                    for u, v in boundary_edges:
                        bot_u = num_verts + u
                        bot_v = num_verts + v
                        wall_faces.append([u, bot_u, bot_v])
                        wall_faces.append([u, bot_v, v])

                    all_faces = faces_front + faces_back + wall_faces
                    mesh = trimesh.Trimesh(vertices=all_vertices, faces=all_faces)
                    mesh.fill_holes()
                    mesh.fix_normals()

                    # 8. Kaide Ekle
                    if add_base:
                        bounds = mesh.bounds
                        width = bounds[1][0] - bounds[0][0]
                        depth = bounds[1][2] - bounds[0][2]
                        base_radius = max(width * 0.45, depth * 1.5)
                        base_height = 4.0
                        base = trimesh.creation.cylinder(radius=base_radius, height=base_height, sections=64)
                        center_x = (bounds[1][0] + bounds[0][0]) / 2.0
                        center_z = (bounds[1][2] + bounds[0][2]) / 2.0
                        base.apply_translation([center_x, bounds[0][1] + 1.0, center_z])
                        mesh = trimesh.util.concatenate([mesh, base])

                    st.success("🎉 Yüksek Çözünürlüklü 3D Biblo Başarıyla Üretildi!")

                    # Model Boyut ve Poligon Bilgisi
                    final_bounds = mesh.bounds
                    f_width = final_bounds[1][0] - final_bounds[0][0]
                    f_depth = final_bounds[1][2] - final_bounds[0][2]
                    f_height = final_bounds[1][1] - final_bounds[0][1]
                    
                    st.info(
                        r"📏 **Model Boyutları:** {:.1f} x {:.1f} x {:.1f} mm  |  "
                        r"🔺 **Poligon Sayısı:** {:,}".format(f_width, f_depth, f_height, len(mesh.faces))
                    )

                    # GLB Önizleme
                    glb_io = io.BytesIO()
                    mesh.export(glb_io, file_type='glb')
                    glb_bytes = glb_io.getvalue()
                    glb_b64 = base64.b64encode(glb_bytes).decode("utf-8")

                    viewer_html = f"""
                    <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                    <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                                  auto-rotate 
                                  camera-controls 
                                  style="width: 100%; height: 420px; background-color: #1a1a1a; border-radius: 12px;">
                    </model-viewer>
                    """
                    components.html(viewer_html, height=440)

                    # İndirme Butonları
                    stl_io = io.BytesIO()
                    mesh.export(stl_io, file_type='stl')
                    stl_bytes = stl_io.getvalue()

                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        st.download_button(
                            label="📥 Yüksek Detaylı STL İndir",
                            data=stl_bytes,
                            file_name="yuksek_kalite_biblo.stl",
                            mime="application/sla",
                            type="primary",
                            use_container_width=True
                        )
                    with col_dl2:
                        st.download_button(
                            label="📥 GLB Önizleme Dosyası İndir",
                            data=glb_bytes,
                            file_name="yuksek_kalite_biblo.glb",
                            mime="model/gltf-binary",
                            use_container_width=True
                        )

            except Exception as e:
                st.error(f"Hata detayı: {str(e)}")
