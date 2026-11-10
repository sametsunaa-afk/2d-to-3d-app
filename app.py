import streamlit as st
import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, distance_transform_edt
import trimesh
import io
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="Gelişmiş 3D Biblo Üretici", page_icon="🗿", layout="wide")

st.title("🗿 Profesyonel 2D'den 3D Biblo Üretici")
st.markdown("Fotoğrafınız pürüzsüzleştirilir, beyaz-siyah dengesizliği giderilir ve heykel formatında katı STL üretilir.")

# Yan Menü Kontrolleri
with st.sidebar:
    st.header("🎛️ Heykel Ayarları")
    target_height = st.slider("Figür Yüksekliği (mm)", 60, 200, 120)
    body_volume = st.slider("Gövde Dolgunluğu (Hacim)", 5, 35, 16, help="Biblonun genel kalınlığı ve sırt bombesi")
    detail_strength = st.slider("Yüz & Kıyafet Detay Gücü", 1, 15, 5, help="Yüz hatlarının ve kıvrımların belirginliği")
    smoothness = st.slider("Yüzey Pürüzsüzlüğü", 1, 5, 2, help="Dikenleri yok edip mermer etkisi verir")
    add_base = st.checkbox("Altına Kaide (Stant) Ekle", value=True)
    
    st.markdown("---")
    st.info("💡 **En İyi Sonuç İçin:** Çiftin fotoğrafını [remove.bg](https://www.remove.bg) adresinden arka plansız (saydam PNG) yapıp yüklerseniz, etraftaki binalar tamamen yok olur ve sadece iki kişinin muazzam heykeli çıkar!")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Fotoğrafı Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (PNG veya JPG)", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("✨ Heykel Kalitesinde 3D STL Üret", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model Önizleme & İndir")
    
    if generate_btn and uploaded_file is not None:
        with st.spinner("Pikseller dengeleniyor, anatomik hacim örülüyor..."):
            try:
                # 1. Görseli Yükle ve Saydamlık Maskesini Çıkar
                img_pil = Image.open(uploaded_file)
                
                # Eğer saydam PNG yüklendiyse arka planı sıfırla
                has_alpha = (img_pil.mode == 'RGBA')
                if has_alpha:
                    alpha = np.array(img_pil.split()[-1], dtype=np.float32) / 255.0
                else:
                    alpha = None

                # 220x220 yüksek kaliteli grid (~100.000 üçgen)
                img_gray = img_pil.convert('L')
                img_gray.thumbnail((220, 220), Image.Resampling.LANCZOS)
                w, h = img_gray.size
                
                # Kontrastı Dengele (Beyaz tişörtün fırlamasını, gözlerin çökmesini engeller)
                img_equalized = ImageOps.equalize(img_gray)
                arr = np.array(img_equalized, dtype=np.float32) / 255.0

                # 2. İki Katmanlı Hacim Ayrıştırma:
                # A) İnce Detay Katmanı (Yüz, saç, kıvrımlar)
                blurred_base = gaussian_filter(arr, sigma=float(smoothness * 2.5))
                high_frequency_details = arr - blurred_base
                z_details = high_frequency_details * float(detail_strength)

                # B) Ana Gövde Hacmi (Anatomik dolgun kavis)
                if alpha is not None:
                    alpha_resized = np.array(Image.fromarray((alpha * 255).astype(np.uint8)).resize((w, h)), dtype=np.float32) / 255.0
                    mask = (alpha_resized > 0.2).astype(np.float32)
                    dist = distance_transform_edt(mask)
                else:
                    # Kenarları hafif yumuşatılmış elips kubbe
                    dist = distance_transform_edt(np.ones((h, w)))
                
                dist_norm = dist / (dist.max() + 1e-6)
                z_body = np.sin(dist_norm * np.pi / 2.0) * float(body_volume)

                # Ön ve Arka Yüzeyleri Birleştir
                z_front = z_body + z_details
                z_back = - (z_body * 0.85) # Arkaya doğru pürüzsüz sırt bombesi

                # 3. 3D Koordinat Ağını Kur
                aspect_ratio = w / h
                x_scale = (target_height * aspect_ratio) / w
                y_scale = target_height / h
                
                x = np.linspace(-w * x_scale / 2.0, w * x_scale / 2.0, w)
                y = np.linspace(h * y_scale / 2.0, -h * y_scale / 2.0, h)
                xx, yy = np.meshgrid(x, y)
                
                top_vertices = np.column_stack((xx.flatten(), yy.flatten(), z_front.flatten()))
                bot_vertices = np.column_stack((xx.flatten(), yy.flatten(), z_back.flatten()))
                all_vertices = np.vstack((top_vertices, bot_vertices))
                
                # Yüzeyleri Üçgenleştir (Watertight / Katı Gövde)
                faces = []
                hw = w * h
                
                for i in range(h - 1):
                    for j in range(w - 1):
                        v0 = i * w + j
                        v1 = i * w + (j + 1)
                        v2 = (i + 1) * w + j
                        v3 = (i + 1) * w + (j + 1)
                        
                        # Ön
                        faces.append([v0, v2, v1])
                        faces.append([v1, v2, v3])
                        # Arka
                        faces.append([hw + v0, hw + v1, hw + v2])
                        faces.append([hw + v1, hw + v3, hw + v2])
                
                # Yan Kenarları Birleştir
                for j in range(w - 1):
                    faces.append([j, j + 1, hw + j])
                    faces.append([j + 1, hw + j + 1, hw + j])
                    t_bot = (h - 1) * w + j
                    faces.append([t_bot, hw + t_bot, t_bot + 1])
                    faces.append([t_bot + 1, hw + t_bot, hw + t_bot + 1])
                
                for i in range(h - 1):
                    t_left = i * w
                    faces.append([t_left, hw + t_left, (i + 1) * w])
                    faces.append([(i + 1) * w, hw + t_left, hw + (i + 1) * w])
                    t_right = i * w + (w - 1)
                    faces.append([t_right, (i + 1) * w + (w - 1), hw + t_right])
                    faces.append([(i + 1) * w + (w - 1), hw + (i + 1) * w + (w - 1), hw + t_right])
                
                mesh = trimesh.Trimesh(vertices=all_vertices, faces=faces)
                mesh.fill_holes()
                mesh.fix_normals()
                
                # 4. Kaide Ekle
                if add_base:
                    bounds = mesh.bounds
                    base_radius = max((bounds[1][0] - bounds[0][0]), (bounds[1][1] - bounds[0][1])) * 0.42
                    base_height = 4.0
                    base = trimesh.creation.cylinder(radius=base_radius, height=base_height, sections=48)
                    base.apply_translation([0, bounds[0][1] + 1.5, bounds[0][2] - (base_height / 2.0)])
                    mesh = trimesh.util.concatenate([mesh, base])
                
                st.success("🎉 Pürüzsüz Katı 3D Modeliniz Başarıyla Üretildi!")
                
                # GLB 3D Önizleme
                glb_io = io.BytesIO()
                mesh.export(glb_io, file_type='glb')
                glb_b64 = base64.b64encode(glb_io.getvalue()).decode("utf-8")
                
                viewer_html = f"""
                <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.3.0/model-viewer.min.js"></script>
                <model-viewer src="data:model/gltf-binary;base64,{glb_b64}" 
                              auto-rotate 
                              camera-controls 
                              style="width: 100%; height: 440px; background-color: #222222; border-radius: 12px;">
                </model-viewer>
                """
                components.html(viewer_html, height=460)
                
                # STL İndir
                stl_io = io.BytesIO()
                mesh.export(stl_io, file_type='stl')
                stl_bytes = stl_io.getvalue()
                
                st.download_button(
                    label="📥 3D Yazıcı İçin Katı STL İndir",
                    data=stl_bytes,
                    file_name="cift_heykelcik_stl.stl",
                    mime="application/sla",
                    type="primary",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"Hata detayı: {str(e)}")
