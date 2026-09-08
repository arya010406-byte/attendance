const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');
const axios = require('axios');
const multer = require('multer');
const FormData = require('form-data');
const fs = require('fs');
require('dotenv').config();

const app = express();

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Serve static assets from root and public directories
app.use(express.static(path.join(__dirname)));
app.use(express.static(path.join(__dirname, 'public')));

// Serve index.html reliably
app.get('/', (req, res) => {
    const rootIndexPath = path.join(__dirname, 'index.html');
    const publicIndexPath = path.join(__dirname, 'public', 'index.html');

    if (fs.existsSync(rootIndexPath)) {
        res.sendFile(rootIndexPath);
    } else if (fs.existsSync(publicIndexPath)) {
        res.sendFile(publicIndexPath);
    } else {
        res.status(404).send("Error: 'index.html' not found in root or public folder.");
    }
});

// MongoDB Atlas / Local Connection setup
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/schoolDB';

mongoose.connect(MONGO_URI)
  .then(() => {
      if (MONGO_URI.includes('mongodb+srv')) {
          console.log('Successfully connected to MongoDB Atlas Cloud!');
      } else {
          console.log('Connected to Local MongoDB (mongodb://127.0.0.1:27017/schoolDB)');
      }
  })
  .catch(err => {
      console.error('MongoDB Connection Failed:', err.message);
  });

const upload = multer({ storage: multer.memoryStorage() });

// Attendance Schema
const AttendanceSchema = new mongoose.Schema({
    className: { type: String, required: true },
    division: { type: String, required: true },
    date: { type: String, required: true },
    records: { type: Map, of: String },
    verifiedAt: { type: Date, default: Date.now }
});
const Attendance = mongoose.model('Attendance', AttendanceSchema);

// Verify Face Route: Forwards webcam capture from website to rgt.py
app.post('/api/auth/verify-face', upload.single('live_photo'), async (req, res) => {
    try {
        if (!req.file) return res.status(400).json({ success: false, message: 'No camera capture received' });

        const formData = new FormData();
        formData.append('live_photo', req.file.buffer, { filename: 'live.jpg', contentType: 'image/jpeg' });

        const pyRes = await axios.post('http://127.0.0.1:5001/scan-and-verify', formData, {
            headers: formData.getHeaders()
        });

        res.json(pyRes.data);
    } catch (error) {
        if (error.response) return res.status(error.response.status).json(error.response.data);
        res.status(500).json({ success: false, message: 'Python verification service offline. Run rgt.py!' });
    }
});

// Attendance Management Routes
app.post('/api/attendance/submit', async (req, res) => {
    try {
        if (mongoose.connection.readyState !== 1) {
            return res.status(500).json({ 
                success: false, 
                message: 'Database not connected. Check your MongoDB connection or .env file!' 
            });
        }

        const { className, division, date, records } = req.body;
        const parsedRecords = typeof records === 'string' ? JSON.parse(records) : records;

        const updatedRecord = await Attendance.findOneAndUpdate(
            { className, division, date },
            { className, division, date, records: parsedRecords },
            { upsert: true, new: true }
        );

        res.status(200).json({ success: true, message: 'Attendance register saved to MongoDB!', data: updatedRecord });
    } catch (error) {
        console.error("Submit Error:", error);
        res.status(500).json({ success: false, message: 'Error saving attendance to database.' });
    }
});

app.get('/api/attendance/:className/:division/:date', async (req, res) => {
    try {
        if (mongoose.connection.readyState !== 1) {
            return res.status(500).json({ success: false, message: 'Database disconnected.' });
        }

        const { className, division, date } = req.params;
        const record = await Attendance.findOne({ className, division, date });
        if (!record) return res.status(404).json({ success: false, message: 'No attendance record found.' });
        res.status(200).json({ success: true, record });
    } catch (error) {
        res.status(500).json({ success: false, message: 'Server error retrieving attendance.' });
    }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Node Server running on http://localhost:${PORT}`));