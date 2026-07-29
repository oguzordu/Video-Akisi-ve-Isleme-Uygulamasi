# Video Upload & Analysis App

## Türkçe

Video yükleyip otomatik analiz yaptırmayı sağlayan, tarayıcıda canlı kamera
önizlemesi de sunan bir uygulama.

### Özellikler

- Analiz için video yükleme
- WebRTC ile canlı kamera önizlemesi
- Analiz sonuçlarının ve meta verilerin daha sonra erişilebilmesi için
  saklanması

### Kullanılan Teknolojiler

- **Backend:** Python (Flask)
- **Video analizi:** Azure Video Indexer API
- **Frontend:** WebRTC ile HTML/CSS/JS
- **Veritabanı:** MongoDB Atlas

### Mimari

Flask backend video yüklemelerini kabul ediyor, analiz için Azure Video
Indexer API'sine gönderiyor ve ortaya çıkan meta veri ile analiz sonuçlarını
MongoDB Atlas'ta saklıyor. Frontend, yükleme akışının yanında canlı kamera
önizlemesi için WebRTC kullanıyor.

---

## English

An app for uploading videos and running automated analysis on them, with a
live camera preview in the browser.

### Features

- Upload a video for analysis
- Live camera preview via WebRTC
- Analysis results and metadata stored for later retrieval

### Tech Stack

- **Backend:** Python (Flask)
- **Video analysis:** Azure Video Indexer API
- **Frontend:** HTML/CSS/JS with WebRTC
- **Database:** MongoDB Atlas

### Architecture

The Flask backend accepts video uploads, sends them to the Azure Video
Indexer API for analysis, and stores the resulting metadata and analysis
results in MongoDB Atlas. The frontend uses WebRTC for a live camera preview
alongside the upload flow.
