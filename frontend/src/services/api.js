import axios from 'axios';

const apiBaseUrl = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 45000,
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (process.env.NODE_ENV === 'development' && !error.message?.includes('timeout')) {
      if (error.response) {
        console.error('API Error:', error.response.status, error.response.data);
      } else if (!error.message?.includes('timeout')) {
        console.error('API Error:', error.message);
      }
    }
    return Promise.reject(error);
  }
);

export const geocode = async (q, limit = 1, countrycodes = 'gb') => {
  const res = await api.get('/v1/geocode', { params: { q, limit, countrycodes } });
  return res.data;
};

export const getCrimes = async (params) => {
  const res = await api.get('/v1/crime', { params });
  return res.data;
};

export const getEvents = async (params) => {
  const res = await api.get('/v1/events', { params });
  return res.data;
};

export const getNews = async (params) => {
  const res = await api.get('/v1/news', { params });
  return res.data;
};

export const getPOIs = async (params) => {
  const res = await api.get('/v1/pois', { params });
  return res.data;
};

export const getSummary = async (params) => {
  const res = await api.get('/v1/summarise', { params });
  return res.data;
};

export const getScores = async (params) => {
  const res = await api.get('/v1/scores', { params });
  return res.data;
};

// New location data endpoint
export const getLocationData = async (params) => {
  const res = await api.get('/v1/location-data', { 
    params,
    timeout: 60000
  });
  return res.data;
};

// User interaction endpoints
export const addInteraction = async (userId, interactionData) => {
  const res = await api.post('/v1/interaction', interactionData, {
    params: { user_id: userId }
  });
  return res.data;
};

export const getUserInteractions = async (userId, params = {}) => {
  const res = await api.get('/v1/interactions', {
    params: { user_id: userId, ...params }
  });
  return res.data;
};

export const getUserPreferences = async (userId) => {
  const res = await api.get('/v1/preferences', {
    params: { user_id: userId }
  });
  return res.data;
};

// User-based recommendations
export const getUserRecommendations = async (userId, params) => {
  const res = await api.get('/v1/user-recommendations', {
    params: { user_id: userId, ...params }
  });
  return res.data;
};

// Chat API endpoints
export const sendChatMessage = async ({ message, lat, lon, location_name, conversation_id }) => {
  const res = await api.post('/v1/chat', {
    message,
    lat,
    lon,
    location_name,
    conversation_id
  });
  return res.data;
};

export const getChatIntents = async () => {
  const res = await api.get('/v1/chat/intents');
  return res.data;
};






