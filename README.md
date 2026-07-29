# Video Upload & Analysis App

An app for uploading videos and running automated analysis on them, with a
live camera preview in the browser.

## Features

- Upload a video for analysis
- Live camera preview via WebRTC
- Analysis results and metadata stored for later retrieval

## Tech Stack

- **Backend:** Python (Flask)
- **Video analysis:** Azure Video Indexer API
- **Frontend:** HTML/CSS/JS with WebRTC
- **Database:** MongoDB Atlas

## Architecture

The Flask backend accepts video uploads, sends them to the Azure Video
Indexer API for analysis, and stores the resulting metadata and analysis
results in MongoDB Atlas. The frontend uses WebRTC for a live camera preview
alongside the upload flow.
