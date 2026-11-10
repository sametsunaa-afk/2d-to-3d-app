import streamlit as st
import tempfile
import os
import io
import trimesh
from gradio_client import Client, handle_file

# Sayfa Ayarları
st.set_page_config(page_title="2D to 3D STL Üretici", page_icon="🗿", layout="wide")

st.title("🗿 Ücretsiz 2D'den 3D'ye STL Üretici")
st.info("🎉 Bu sürümde hiçbir ücretli üyelik veya API Key gerekmez! Açık kaynaklı yapay zeka kullanılmaktadır.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Fotoğrafı Yükleyin")
    uploaded_file = st.file_uploader("Görsel seçin (JPG veya PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Yüklenen Görsel", use_container_width=True)
        generate_btn = st.button("🚀 3D Modeli ve Arkasını Oluştur", type="primary")
    else:
        generate_btn = False

with col2:
    st.subheader("2. 3D Model ve STL İndirme")
    
    if generate_btn and uploaded_file is not None:
        with st.spinner("Açık kaynaklı yapay zeka modeli örüyor... (Lütfen 1-2 dakika bekleyin)"):
            try:
                # Geçici görsel dosyası oluştur
                suffix = os.path.splitext(uploaded_file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name

                # Stability AI TripoSR yapay zekasına ücretsiz bağlan
                client = Client("stabilityai/TripoSR")
                result = client.predict(
                    image=handle_file(tmp_path),
                    do_remove_background=True,
                    foreground_ratio=0.85,
                    mc_resolution=256,
                    api_name="/generate_mesh"
                )

                # Üretilen 3D model dosyasını al
                model_file_path = result[0] if isinstance(result, (list, tuple)) else result

                if os.path.exists(model_file_path):
                    st.success("🎉 3D Model başarıyla üretildi!")

                    # Modeli STL formatına dönüştür
                    scene_or_mesh = trimesh.load(model_file_path)
                    if isinstance(scene_or_mesh, trimesh.Scene):
                        meshes = [g for g in scene_or_mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
                        solid_mesh = trimesh.util.concatenate(meshes)
                    else:
                        solid_mesh = scene_or_mesh

                    stl_io = io.BytesIO()
                    solid_mesh.export(stl_io, file_type='stl')
                    stl_bytes = stl_io.getvalue()

                    # İndirme Butonu
                    st.download_button(
                        label="📥 3D Yazıcı İçin STL İndir",
                        data=stl_bytes,
                        file_name="3d_baski_modeli.stl",
                        mime="application/sla",
                        type="primary",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"İşlem sırasında bir hata oluştu: {str(e)}")
