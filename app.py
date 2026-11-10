import streamlit as st
import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, distance_transform_edt
from collections import Counter
import trimesh
import io
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="Saf Silüet 3D Biblo Üretici", page_icon="🗿", layout="wide")

st.title("🗿 Çerçevesiz, Saf Kişi Silüeti 3D Biblo Üretici")
st.markdown("Arka plandaki tüm dikdörtgen çerçeve atılır; **yalnızca iki kişinin vücut hatları** katı bir heykelcik olarak üretilir.")

# Yan Menü Kontrolleri
with st.sidebar:
    st.header("🎛️ Biblo Ayarları")
    target_height = st.slider("Figür Boyu (mm)", 60, 200, 120, help="Yazıcıdan çıkacak figürün boyu")
    body_thickness = st.slider("Figür Kalınlığı / Hacmi", 4, 30, 14, help="Kişilerin ön ve arka vücut dolgunluğu")
    detail_strength = st.slider("Yüz & Kıyafet Detay Gücü", 1, 15, 6, help="Yüz hatlarının ve tişörtün belirginliği")
    smoothness = st.slider("Pürüzsüzlük", 1, 5, 2, help="Yüzeydeki parazitleri temizler")
    add_base = st.checkbox("Ayakların Altına Yuvarlak Kaide Ekle", value=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Saydam PNG Görselini Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (Arka plansız PNG)", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("✂️ Çerçevesiz 3D Figürü Üret", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model Önizleme & STL İndir")
    
    if generate_btn and uploaded_file is not None:
        with st.spinner("Dikdörtgen çerçeve kesilip atılıyor, sadece kişiler 3D örülüyor..."):
            try:
                # 1. Görseli Yükle ve Saydamlık Katmanını Oku
                img_pil = Image.open(uploaded_file)
                
                # Çözünürlüğü optimize et (Hızlı ve detaylı)
                img_pil.thumbnail((220, 220), Image.Resampling.LANCZOS)
                w, h = img_pil.size
                
                # Saydamlık Maskesini Çıkar (Kişiler = 1, Arka plan = 0)
                if img_pil.mode == 'RGBA':
                    alpha = np.array(img_pil.split()[-1], dtype=np.float32) / 255.0
                    mask = (alpha > 0.15)
                else:
                    # Eğer JPG yüklendiyse siyaha yakın yerleri arka plan say
                    gray_temp = np.array(img_pil.convert('L'), dtype=np.float32)
                    mask = (gray_temp > 20)

                if np.sum(mask) == 0:
                    st.error("Görselde kişi alanı tespit edilemedi! Lütfen arka planı saydam bir PNG yükleyin.")
                else:
                    # 2. Yüz ve Kıyafet Detaylarını Hesapla
                    img_gray = img_pil.convert('L')
                    img_eq = ImageOps.equalize(img_gray)
                    arr = np.array(img_eq, dtype=np.float32) / 255.0

                    blurred = gaussian_filter(arr, sigma=float(smoothness * 2.0))
                    high_pass = arr - blurred
                    z_details = high_pass * float(detail_strength)

                    # 3. Kişilerin Vücut Hacmi (Kenardan merkeze doğru dolgunlaşan gövde)
                    dist = distance_transform_edt(mask)
                    dist_norm = dist / (dist.max() + 1e-6)
                    # Ön taraf: Vücut bombesi + Yüz detayları
                    z_front = (np.sin(dist_norm * np.pi / 2.0) * float(body_thickness)) + z_details + 0.8
                    # Arka taraf: Pürüzsüz sırt kubbesi
                    z_back = - (np.sin(dist_norm * np.pi / 2.0) * float(body_thickness) * 0.85) - 0.8

                    # 4. Koordinatları Ölçekle
                    aspect_ratio = w / h
                    x_scale = (target_height * aspect_ratio) / w
                    y_scale = target_height / h
                    
                    x = np.linspace(-w * x_scale / 2.0, w * x_scale / 2.0, w)
                    y = np.linspace(h * y_scale / 2.0, -h * y_scale / 2.0, h)
                    xx, yy = np.meshgrid(x, y)

                    # 5. SADECE KİŞİLERİN OLDUĞU PİKSELLERE NOKTA OLUŞTUR (Çerçeveyi Yok Et)
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

                    # 6. Sadece Kişilerin İçini Üçgenle
                    faces_front = []
                    faces_back = []

                    for i in range(h - 1):
                        for j in range(w - 1):
                            v0 = vertex_map[i, j]
                            v1 = vertex_map[i, j + 1]
                            v2 = vertex_map[i + 1, j]
                            v3 = vertex_map[i + 1, j + 1]

                            # 4 köşe de kişinin vücudunun içindeyse yüzey ör
                            if v0 != -1 and v1 != -1 and v2 != -1 and v3 != -1:
                                # Ön yüz üçgenleri
                                faces_front.append([v0, v2, v1])
                                faces_front.append([v1, v2, v3])
                                # Arka yüz üçgenleri
                                faces_back.append([num_verts + v0, num_verts + v1, num_verts + v2])
                                faces_back.append([num_verts + v1, num_verts + v3, num_verts + v2])

                    # 7. Yan Duvarları Ör (Ön ile Arkayı Vücut Silüeti Boyunca Dik ve Kapat)
                    edge_counts = Counter()
                    for f in faces_front:
                        edge_counts[(f[0], f[1])] += 1
                        edge_counts[(f[1], f[2])] += 1
                        edge_counts[(f[2], f[0])] += 1

                    # Yalnızca dış silüet kenarlarını bul
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

                    # 8. Kaide Ekle (Ayakların tam altına)
                    if add_base:
                        bounds = mesh.bounds
                        width = bounds[1][0] - bounds[0][0]
                        depth = bounds[1][2] - bounds[0][2]
                        base_radius = max(width * 0.45, depth * 1.5)
                        base_height = 4.0
                        base = trimesh.creation.cylinder(radius=base_radius, height=base_height, sections=48)
                        center_x = (bounds[1][0] + bounds[0][0]) / 2.0
                        center_z = (bounds[1][2] + bounds[0][2]) / 2.0
                        base.apply_translation([center_x, bounds[0][1] + 1.0, center_z])
                        mesh = trimesh.util.concatenate([mesh, base])

                    st.success("🎉 Çerçevesiz, Gerçek 3D Kişi Heykelciği Hazır!")

                    # GLB Önizleme
                    glb_io = io.BytesIO()
                    mesh.export(glb_io, file_type='glb')
                    glb_b64 = base64.b64encode(glb_io.getvalue()).decode("utf-8")

                    viewer_html = f"""
                    <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                    <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                                  auto-rotate 
                                  camera-controls 
                                  style="width: 100%; height: 460px; background-color: #1a1a1a; border-radius: 12px;">
                    </model-viewer>
                    """
                    components.html(viewer_html, height=480)

                    # STL İndir
                    stl_io = io.BytesIO()
                    mesh.export(stl_io, file_type='stl')
                    stl_bytes = stl_io.getvalue()

                    st.download_button(
                        label="📥 3D Yazıcı İçin Katı STL İndir (Çerçevesiz)",
                        data=stl_bytes,
                        file_name="cift_siluet_biblo.stl",
                        mime="application/sla",
                        type="primary",
                        use_container_width=True
                    )

            except Exception as e:
                st.error(f"Hata detayı: {str(e)}")
