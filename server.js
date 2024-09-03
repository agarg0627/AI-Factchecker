const express = require('express');
const cors = require('cors');
const axios = require('axios'); // Using axios to handle external requests

const app = express();

const corsOptions = {
    origin: '*', // Adjust this as needed
    methods: 'GET,POST',
    allowedHeaders: 'Content-Type,Authorization',
    credentials: true,
};

app.use(cors(corsOptions)); // Use CORS middleware with options

// Proxy route to fetch data from Google Drive
app.get('/proxy-data', async (req, res) => {
    const fileId = '1Lv-XWWRbR24WNf7HhSEDHS31srA3QnE5';
    const googleDriveUrl = `https://drive.google.com/uc?export=download&id=${fileId}`;

    try {
        const response = await axios.get(googleDriveUrl);
        res.json(response.data);
    } catch (error) {
        res.status(500).send('Error fetching data from Google Drive');
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});


