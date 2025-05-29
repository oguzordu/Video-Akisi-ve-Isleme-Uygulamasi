import os
from flask import Flask, request, jsonify, render_template_string, g
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId # ObjectId'leri string'e çevirmek için gerekebilir (şimdilik kullanılmıyor)
import datetime

load_dotenv()

app = Flask(__name__)

# MongoDB Ayarları
MONGODB_URI = os.getenv('MONGODB_CONNECTION_STRING')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME')

_mongo_client = None

def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        if not MONGODB_URI:
            print("HATA: MONGODB_CONNECTION_STRING ortam değişkeni ayarlanmamış.")
            return None
        try:
            _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            _mongo_client.admin.command('ping') 
            print("MongoDB'ye başarıyla bağlandı!")
        except Exception as e:
            print(f"MongoDB bağlantı hatası: {e}")
            _mongo_client = None
    return _mongo_client

def get_db_collection(collection_name='videos'):
    client = get_mongo_client()
    if client and MONGODB_DB_NAME:
        db = client[MONGODB_DB_NAME]
        return db[collection_name]
    return None

# .env'den Video Indexer bilgileri
SUBSCRIPTION_KEY = os.getenv('VIDEO_INDEXER_SUBSCRIPTION_KEY')
LOCATION = os.getenv('VIDEO_INDEXER_LOCATION')
ACCOUNT_ID = os.getenv('VIDEO_INDEXER_ACCOUNT_ID')

# Access Token Al
def get_access_token():
    if not all([SUBSCRIPTION_KEY, LOCATION, ACCOUNT_ID]):
        print("HATA: Azure Video Indexer yapılandırma anahtarları eksik.")
        return None
    url = f"https://api.videoindexer.ai/Auth/{LOCATION}/Accounts/{ACCOUNT_ID}/AccessToken?allowEdit=true"
    headers = {"Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text.replace('"', '')
    except requests.exceptions.RequestException as e:
        print(f"Azure token alma hatası: {e}")
        return None

@app.route('/upload', methods=['POST'])
def upload_video_route():
    if 'video' not in request.files:
        return jsonify({'error': 'Video dosyası gerekli'}), 400
    video_file = request.files['video']
    
    access_token = get_access_token()
    if not access_token:
        return jsonify({'error': 'Azure Video Indexer token alınamadı veya yapılandırma eksik.'}), 500
        
    upload_url = f"https://api.videoindexer.ai/{LOCATION}/Accounts/{ACCOUNT_ID}/Videos?accessToken={access_token}&name={video_file.filename}&privacy=Private&videoUrl="
    files = {'file': (video_file.filename, video_file.stream, video_file.mimetype)}
    
    try:
        azure_response = requests.post(upload_url, files=files, timeout=30)
        azure_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Azure'a yükleme sırasında ağ hatası: {e}")
        return jsonify({"error": "Azure'a yükleme sırasında ağ hatası", "details": str(e)}), 500

    if azure_response.status_code != 200:
        return jsonify({"error": "Azure'a yükleme başarısız oldu", "status_code": azure_response.status_code, "details": azure_response.text}), 500
    
    video_data = azure_response.json()
    video_id_from_azure = video_data.get('id')
    if not video_id_from_azure:
        return jsonify({'error': 'Azure yanıtından video ID alınamadı', 'details': video_data}), 500
        
    filename = video_file.filename
    upload_date = datetime.datetime.utcnow()

    videos_collection = get_db_collection('videos')
    if videos_collection is None:
        return jsonify({'error': 'Veritabanı bağlantısı/collection alınamadı'}), 500
        
    video_document = {
        'video_id': video_id_from_azure,
        'filename': filename,
        'upload_date': upload_date,
        'status': 'Uploaded'
    }
    try:
        result = videos_collection.insert_one(video_document)
        print(f"MongoDB'ye eklendi, _id: {result.inserted_id}, video_id: {video_id_from_azure}")
    except Exception as e:
        print(f"MongoDB kayıt hatası: {e}")
        return jsonify({'error': 'Veritabanına kayıt sırasında hata oluştu', 'details': str(e)}), 500

    return jsonify({'message': 'Video yüklendi ve veritabanına kaydedildi', 'video_id': video_id_from_azure})

@app.route('/')
def home():
    videos_collection = get_db_collection('videos')
    video_list = []
    if videos_collection is not None:
        try:
            fetched_videos = list(videos_collection.find().sort('upload_date', -1))
            for video in fetched_videos:
                video['_id'] = str(video['_id'])
                if isinstance(video.get('upload_date'), datetime.datetime):
                     video['upload_date'] = video['upload_date'].strftime("%Y-%m-%d %H:%M:%S UTC")
                video_list.append(video)
        except Exception as e:
            print(f"Videoları MongoDB'den çekerken hata: {e}")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Azure Video Indexer Demo - MongoDB</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f6; color: #333; }
            .container { max-width: 900px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2, h3 { color: #2c3e50; margin-top: 0; }
            .section { margin-bottom: 30px; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px; background-color: #fdfdfd; }
            .section h3 { margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }
            label { display: block; margin-bottom: 8px; font-weight: 500; }
            input[type=\"file\"] { margin-bottom: 15px; padding: 8px; border: 1px solid #ccc; border-radius: 4px; width: calc(100% - 20px); }
            button, input[type=\"submit\"] {
                background-color: #3498db; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em;
                transition: background-color 0.3s ease; margin-right: 10px; margin-top: 5px;
            }
            button.danger { background-color: #e74c3c; }
            button.danger:hover { background-color: #c0392b; }
            button:hover, input[type=\"submit\"]:hover { background-color: #2980b9; }
            button:disabled { background-color: #bdc3c7; cursor: not-allowed; }
            video { border: 1px solid #ddd; border-radius: 4px; background-color: #000; }
            #uploadStatus p, #liveStatus p { margin: 10px 0; padding: 10px; border-radius: 4px; }
            #uploadStatus .success, #liveStatus .success { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
            #uploadStatus .error, #liveStatus .error { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
            th { background-color: #ecf0f1; color: #34495e; }
            td a { color: #3498db; text-decoration: none; }
            td a:hover { text-decoration: underline; }
            hr { border: 0; height: 1px; background-color: #e0e0e0; margin: 30px 0; }
            .video-container video { margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Azure Video Indexer Demo Uygulaması (MongoDB ile)</h2>

            <div class="section">
                <h3>1. Video Yükle (Dosyadan Seç)</h3>
                <form id="uploadForm" method="post" enctype="multipart/form-data" action="{{ url_for('upload_video_route') }}">
                    <label for="videoInput">Bilgisayarınızdan bir video dosyası seçin (örn: .mp4, .mov):</label>
                    <input type="file" id="videoInput" name="video" accept="video/*" required>
                    <button type="submit">Seçilen Videoyu Yükle</button>
                </form>
                <div id="uploadStatus"></div>
            </div>
            
            <hr>

            <div class="section">
                <h3>2. Canlı Kamera Akışı (WebRTC Demo)</h3>
                <p>Bu bölüm, WebRTC kullanarak tarayıcınızdan anlık canlı kamera görüntüsünü gösterir. Bu akış kaydedilmez veya analiz edilmez, sadece gerçek zamanlı video akışı teknolojisini demonstre eder.</p>
                <button id="startLive">Canlı Akışı Başlat</button>
                <button id="stopLive" style="display:none;" class="danger">Canlı Akışı Durdur</button>
                <div id="liveSection" style="display:none; margin-top:10px;" class="video-container">
                    <video id="liveVideo" width="320" height="240" autoplay muted playsinline></video>
                </div>
                <div id="liveStatus"></div>
            </div>

            <hr>

            <div class="section">
                <h3>3. Yüklenen Videolar (Veritabanı Kayıtları)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Video ID (Azure)</th>
                            <th>Dosya Adı</th>
                            <th>Yükleme Tarihi</th>
                            <th>Durum</th>
                            <th>İşlem</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for video_doc in videos %}
                        <tr>
                            <td>{{ video_doc.video_id }}</td>
                            <td>{{ video_doc.filename }}</td>
                            <td>{{ video_doc.upload_date }}</td>
                            <td>{{ video_doc.status }}</td>
                            <td><a href="{{ url_for('get_result', video_id=video_doc.video_id) }}" target="_blank">Analizi Gör</a></td>
                        </tr>
                        {% else %}
                        <tr><td colspan="5">Henüz veritabanına kaydedilmiş video bulunmamaktadır.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
                 <button onclick="location.reload()" style="margin-top:15px;">Listeyi Yenile</button>
            </div>
        </div>

        <script>
        let currentLiveStream; // Canlı yayın için stream

        const videoInput = document.getElementById('videoInput');
        const uploadForm = document.getElementById('uploadForm');
        const uploadStatus = document.getElementById('uploadStatus');
        
        const startLiveBtn = document.getElementById('startLive');
        const stopLiveBtn = document.getElementById('stopLive');
        const liveSection = document.getElementById('liveSection');
        const liveVideo = document.getElementById('liveVideo');
        const liveStatus = document.getElementById('liveStatus');

        startLiveBtn.onclick = async () => {
            liveStatus.innerHTML = '';
            liveSection.style.display = 'block';
            try {
                currentLiveStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                liveVideo.srcObject = currentLiveStream;
                startLiveBtn.style.display = 'none';
                stopLiveBtn.style.display = 'inline-block';
                liveStatus.innerHTML = '<p class="success">Canlı akış başlatıldı.</p>';
            } catch (e) {
                liveStatus.innerHTML = '<p class="error">Canlı yayın için kamera erişimi reddedildi veya bir hata oluştu: ' + e.message + '</p>';
                liveSection.style.display = 'none';
            }
        };

        stopLiveBtn.onclick = () => {
            if (currentLiveStream) {
                currentLiveStream.getTracks().forEach(track => track.stop());
            }
            liveVideo.srcObject = null;
            liveSection.style.display = 'none';
            startLiveBtn.style.display = 'inline-block';
            stopLiveBtn.style.display = 'none';
            liveStatus.innerHTML = '<p class="success">Canlı akış durduruldu.</p>';
        };

        uploadForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const formData = new FormData(uploadForm);
            uploadStatus.innerHTML = '<p>Yükleniyor...</p>';
            try {
                const response = await fetch("{{ url_for('upload_video_route') }}", { method: 'POST', body: formData });
                const result = await response.json();
                if (response.ok && result.video_id) {
                    uploadStatus.innerHTML = `<p class="success">${result.message} (Video ID: ${result.video_id}). <a href="/result/${result.video_id}" target="_blank">Analizi Gör</a></p><p><button onclick="location.reload()">Listeyi Güncelle</button></p>`;
                    videoInput.value = "";
                } else {
                    const errorMessage = result.error || 'Bilinmeyen bir hata oluştu.';
                    const errorDetails = result.details || (result.status_code ? `HTTP Status: ${result.status_code}` : (result.message || ''));
                    uploadStatus.innerHTML = `<p class="error">Hata: ${errorMessage} ${errorDetails}</p>`;
                }
            } catch (error) {
                uploadStatus.innerHTML = `<p class="error">Yükleme sırasında bir ağ hatası veya cevap işleme hatası oluştu: ${error}</p>`;
            }
        });
        </script>
    </body>
    </html>
    """, videos=video_list)

@app.route('/result/<video_id>', methods=['GET'])
def get_result(video_id):
    access_token = get_access_token()
    if not access_token:
        return jsonify({'error': 'Azure Video Indexer token alınamadı veya yapılandırma eksik.'}), 500
        
    url = f"https://api.videoindexer.ai/{LOCATION}/Accounts/{ACCOUNT_ID}/Videos/{video_id}/Index?accessToken={access_token}"
    
    try:
        azure_response = requests.get(url, timeout=20) 
        azure_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Azure'dan analiz alınırken ağ hatası: {e}")
        return jsonify({'error': 'Azure\'dan analiz alınırken ağ hatası', 'details': str(e)}),500

    if azure_response.status_code != 200:
        return jsonify({'error': 'Azure\'dan analiz alınamadı', 'status_code': azure_response.status_code, 'details': azure_response.text}), 500
    
    analysis_data = azure_response.json()
    
    # Analiz verisinden Anahtar Kelimeleri ve Konuları ayıklama
    extracted_keywords = []
    extracted_topics = []
    
    # JSON yapısı videodan videoya veya API versiyonuna göre değişebilir, kontroller ekleyelim
    # insights genellikle summarizedInsights içinde veya doğrudan olabilir.
    insights = analysis_data.get('videos', [{}])[0].get('insights', {})
    if not insights: # Eğer ana 'insights' yoksa, eski bir yapı veya farklı bir JSON formatı olabilir.
        insights = analysis_data.get('summarizedInsights', {})

    if insights:
        keywords_data = insights.get('keywords', [])
        for kw in keywords_data:
            extracted_keywords.append(kw.get('text', '-')) # Sadece text'i al, yoksa '-' koy
            
        topics_data = insights.get('topics', [])
        for topic in topics_data:
            extracted_topics.append(topic.get('name', '-')) # Sadece name'i al, yoksa '-' koy
            
    # MongoDB'de durumu güncelle (Bu kısım aynı kalıyor)
    videos_collection = get_db_collection('videos')
    if videos_collection is None:
        print("Analiz sonucu alınırken veritabanı collection alınamadı, durum güncellenemedi.")
    else:
        try:
            update_result = videos_collection.update_one(
                {'video_id': video_id},
                {'$set': {'status': 'Analyzed'}}
            )
            if update_result.matched_count > 0:
                print(f"Video {video_id} durumu MongoDB'de 'Analyzed' olarak güncellendi.")
            else:
                print(f"MongoDB'de {video_id} ID'li video bulunamadı, durum güncellenemedi.")
        except Exception as e:
            print(f"MongoDB durum güncelleme hatası: {e}")

    # Şablona göndermek için context oluştur
    template_context = {
        "video_id": video_id,
        "keywords": extracted_keywords,
        "topics": extracted_topics,
        "full_analysis_json": analysis_data # Ham JSON'u da hala gönderebiliriz, belki alta bir yere koyarız
    }
    
    # Şimdilik basit bir HTML stringi içinde gösterelim, daha sonra bunu render_template_string'e taşıyacağız.
    # Bu kısım bir sonraki adımda render_template_string içinde güncellenecek.
    html_content = f"""    <h1>Analiz Sonuçları: {video_id}</h1>
    <h2>Anahtar Kelimeler</h2>
    <ul>{"<li>" + "</li><li>".join(extracted_keywords) + "</li>" if extracted_keywords else "<li>Bulunamadı</li>"}</ul>
    <h2>Konular</h2>
    <ul>{"<li>" + "</li><li>".join(extracted_topics) + "</li>" if extracted_topics else "<li>Bulunamadı</li>"}</ul>
    <hr>
    <h3>Ham Analiz Verisi (JSON)</h3>
    <pre>{analysis_data}</pre>
    """
    # return html_content # Direkt HTML döndürmek yerine render_template_string kullanacağız.
    # Geçici olarak, sadece JSON döndürmeye devam edelim ki adımları tek tek görelim.
    # Bir sonraki adımda bu HTML'i render_template_string ile birleştireceğiz.
    # return jsonify(analysis_data) # ESKİ HALİ

    # Yeni hali: Ayıklanmış verilerle birlikte render_template_string kullanacağız.
    # Şimdilik, '/result/' sayfası için ayrı bir HTML yapısı oluşturalım ve render_template_string kullanalım.
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Analiz Sonuçları - {{ video_id }}</title>
        <style>
        {% raw %}
            body { font-family: sans-serif; margin: 20px; background-color: #f4f7f6; color: #333; }
            .container { max-width: 800px; margin: 20px auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1, h2, h3 { color: #2c3e50; }
            ul { list-style-type: square; padding-left: 20px; }
            li { margin-bottom: 5px; }
            pre { background-color: #eee; padding: 10px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
            a { color: #3498db; text-decoration: none; }
            a:hover { text-decoration: underline; }
        {% endraw %}
        </style>
    </head>
    <body>
        <div class="container">
            <p><a href="{{ url_for('home') }}">&laquo; Ana Sayfaya Dön</a></p>
            <h1>Video Analiz Sonuçları</h1>
            <p><strong>Video ID:</strong> {{ video_id }}</p>

            <h2>Tespit Edilen Anahtar Kelimeler</h2>
            {% if keywords %}
                <ul>
                    {% for keyword in keywords %}
                        <li>{{ keyword }}</li>
                    {% endfor %}
                </ul>
            {% else %}
                <p>Bu video için anahtar kelime bulunamadı.</p>
            {% endif %}

            <h2>Tespit Edilen Konular</h2>
            {% if topics %}
                <ul>
                    {% for topic in topics %}
                        <li>{{ topic }}</li>
                    {% endfor %}
                </ul>
            {% else %}
                <p>Bu video için konu bulunamadı.</p>
            {% endif %}
            
            <hr style="margin: 30px 0;">
            <h3>Ham Analiz Verisi (JSON)</h3>
            <details>
                <summary>Göstermek için tıkla</summary>
                <pre>{{ full_analysis_json | tojson(indent=2) }}</pre>
            </details>
        </div>
    </body>
    </html>
    """, video_id=video_id, keywords=extracted_keywords, topics=extracted_topics, full_analysis_json=analysis_data)

if __name__ == '__main__':
    app.run(debug=True) 