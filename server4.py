#!/usr/bin/env python3
"""
Servidor HTTPS Local - Versão Final com Google Maps
Arquivo: https_demo_server_final.py

Instruções rápidas:
- Salve este arquivo e execute com Python 3.8+:
    python https_demo_server_final.py

- O servidor tentará gerar um certificado autofirmado (requer pacote `cryptography`).
  Se não quiser instalar, abra em HTTP: http://127.0.0.1:8000
- Página principal: https://127.0.0.1:8443  (ou http://127.0.0.1:8000 se HTTPS não iniciado)

AVISO IMPORTANTE:
Este código serve uma página que pede permissões (localização, câmera, microfone) e salva
os dados localmente em `collected_data/collected.jsonl`.
Use apenas em ambiente local e com seu próprio consentimento. Não use para coletar dados de
outras pessoas sem permissão.
"""

from decouple import config
import http.server
import socketserver
import ssl
import threading
import json
import datetime
import sys
from pathlib import Path
from http import HTTPStatus

# Configurações
HOST = '0.0.0.0'
HTTP_PORT = 8000
HTTPS_PORT = 8443
LOG_DIR = Path('collected_data')
LOG_DIR.mkdir(exist_ok=True)
CERT_FILE = Path('cert.pem')
KEY_FILE = Path('key.pem')

# HTML (mantive o visual e conteúdo conforme solicitado; JS inclui coleta aprimorada)
# === ATENÇÃO: substitua 'REPLACE_WITH_YOUR_KEY' pela sua chave real do Google Maps API ===
HTML_CONTENT = (r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demonstração Completa - Coleta de Dados do Dispositivo</title>
    <style>
        /* Estilos idênticos ao design solicitado, com ajustes de responsividade/overflow */
        * { margin:0; padding:0; box-sizing:border-box; }
        html, body { width:100%; overflow-x:hidden; } /* evita overflow lateral em celulares */
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height:100vh; padding:20px; color:#333; }
        .container { width:100%; max-width:1200px; margin:0 auto; background: rgba(255,255,255,0.95); border-radius:20px; box-shadow:0 20px 60px rgba(0,0,0,0.15); overflow:hidden; backdrop-filter: blur(10px); padding-bottom:20px; }
        .header { background: linear-gradient(45deg, #ff6b6b, #ee5a24); color:white; padding:40px 30px; text-align:center; position:relative; overflow:hidden; }
        .header::before { content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background:radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%); animation: rotate 20s linear infinite; }
        .header h1 { font-size:3em; margin-bottom:15px; text-shadow:3px 3px 6px rgba(0,0,0,0.3); position:relative; z-index:2; }
        .header p { font-size:1.3em; opacity:0.95; position:relative; z-index:2; }
        .warning { background: linear-gradient(45deg, rgba(255,193,7,0.2), rgba(255,152,0,0.2)); border-left:5px solid #ffc107; padding:20px; margin:25px; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1); }
        .content { padding:40px; }
        .info-section { background: linear-gradient(145deg,#f8f9fa,#e9ecef); border-radius:20px; padding:30px; margin:25px 0; border:2px solid #dee2e6; box-shadow:0 10px 30px rgba(0,0,0,0.1); transition: transform 0.3s ease; }
        .info-section:hover { transform: translateY(-5px); }
        .info-title { color:#495057; font-size:1.5em; margin-bottom:20px; font-weight:bold; display:flex; align-items:center; gap:10px; }
        .info-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap:15px; }
        .info-item { background:white; padding:15px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 3px 10px rgba(0,0,0,0.1); transition: all 0.3s ease; gap:10px; min-width:0; overflow:hidden; }
        .info-item:hover { transform: translateX(5px); box-shadow:0 5px 20px rgba(0,0,0,0.15); }
        .info-label { font-weight:bold; color:#6c757d; display:flex; align-items:center; gap:8px; flex:0 0 auto; margin-right:8px; min-width:0; }
        .info-value { color:#495057; font-weight:500; text-align:right; max-width:70%; word-wrap:break-word; word-break:break-word; overflow-wrap:break-word; white-space:normal; }
        .demo-buttons { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap:15px; margin:30px 0; }
        .demo-btn { background: linear-gradient(45deg,#667eea,#764ba2); color:white; border:none; padding:16px 20px; border-radius:50px; font-size:1.05em; font-weight:bold; cursor:pointer; transition: all 0.3s ease; box-shadow:0 8px 25px rgba(102,126,234,0.4); position:relative; overflow:hidden; min-height:56px; display:flex; align-items:center; justify-content:center; text-align:center; }
        .demo-btn::before { content:''; position:absolute; top:50%; left:50%; width:0; height:0; background: rgba(255,255,255,0.12); border-radius:50%; transform: translate(-50%,-50%); transition: width 0.4s ease, height 0.4s ease; }
        .demo-btn:hover::before { width:260px; height:260px; }
        .demo-btn:hover { transform: translateY(-3px) scale(1.02); box-shadow:0 12px 30px rgba(102,126,234,0.5); }
        .location-btn { background: linear-gradient(45deg,#28a745,#20c997); box-shadow:0 8px 25px rgba(40,167,69,0.35); }
        .camera-btn { background: linear-gradient(45deg,#dc3545,#fd7e14); box-shadow:0 8px 25px rgba(220,53,69,0.35); }
        .mic-btn { background: linear-gradient(45deg,#6f42c1,#e83e8c); box-shadow:0 8px 25px rgba(111,66,193,0.35); }
        .location-info,.camera-section,.mic-section { background: linear-gradient(145deg,#e8f5e8,#d4edda); border:3px solid #28a745; border-radius:20px; padding:20px; margin:20px 0; display:none; box-shadow:0 10px 30px rgba(40,167,69,0.12); }
        .camera-section { background: linear-gradient(145deg,#ffe8e8,#f8d7da); border-color:#dc3545; box-shadow:0 10px 30px rgba(220,53,69,0.12); }
        .mic-section { background: linear-gradient(145deg,#f3e8ff,#e2d9f3); border-color:#6f42c1; box-shadow:0 10px 30px rgba(111,66,193,0.12); }
        #map { width:100%; height:320px; background: linear-gradient(145deg,#f0f0f0,#e0e0e0); border-radius:12px; display:flex; align-items:center; justify-content:center; margin:16px 0; font-size:1.05em; color:#666; box-shadow: inset 0 5px 15px rgba(0,0,0,0.06); }
        #camera-video { width:100%; max-width:100%; height:auto; max-height:420px; background:#000; border-radius:12px; margin:12px 0; display:block; box-shadow:0 10px 30px rgba(0,0,0,0.2); }
        .status { padding:12px 14px; border-radius:10px; margin:12px 0; font-weight:bold; font-size:1em; display:flex; align-items:center; gap:10px; }
        .status.success { background: linear-gradient(45deg,#d4edda,#c3e6cb); color:#155724; border:2px solid #c3e6cb; }
        .status.error { background: linear-gradient(45deg,#f8d7da,#f5c6cb); color:#721c24; border:2px solid #f5c6cb; }
        .footer { background: linear-gradient(45deg,#343a40,#495057); color:white; padding:20px; text-align:center; border-radius:0 0 20px 20px; margin-top:20px; }
        .pulse { animation: pulse 2s infinite; }
        .https-success { background: linear-gradient(45deg,#28a745,#20c997); color:white; padding:14px; margin:20px; border-radius:12px; text-align:center; font-weight:bold; font-size:1.05em; box-shadow:0 10px 30px rgba(40,167,69,0.18); }
        .fingerprint-section { background: linear-gradient(145deg,#fff3e0,#ffe0b2); border:3px solid #ff9800; border-radius:20px; padding:20px; margin:20px 0; box-shadow:0 10px 30px rgba(255,152,0,0.12); }
        .audio-visualizer { width:100%; height:100px; background: linear-gradient(90deg,#ff6b6b,#4ecdc4); border-radius:10px; margin:12px 0; display:flex; align-items:end; justify-content:center; padding:10px; gap:2px; }
        .bar { width:4px; background: rgba(255,255,255,0.8); border-radius:2px; transition: height 0.1s ease; }
        @keyframes pulse { 0%{opacity:1;transform:scale(1);}50%{opacity:0.7;transform:scale(1.05);}100%{opacity:1;transform:scale(1);} }
        @keyframes rotate { from{transform:rotate(0deg);} to{transform:rotate(360deg);} }

        /* Mobile adjustments - garante que labels/values quebrem sem causar overflow */
        @media (max-width:768px) {
            .header h1{font-size:2em}
            .content{padding:16px}
            .info-grid{grid-template-columns:1fr}
            .demo-buttons{grid-template-columns:1fr}
            .info-item{flex-direction:column; align-items:flex-start; gap:6px;}
            .info-label{width:100%; margin-bottom:4px; font-size:0.95em;}
            .info-value{max-width:100%; width:100%; text-align:left; white-space:normal; word-break:break-word; overflow-wrap:break-word;}
            .container { padding: 12px; border-radius:14px; }
            #map { height:260px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Coleta Completa de Dados</h1>
            <p>Demonstração: O que sites podem descobrir sobre VOCÊ</p>
        </div>

        <div class="content">
            <div class="https-success">
                🔒 ✅ SERVIDOR FUNCIONANDO! Todas as funcionalidades ativas!
            </div>

            <div class="warning">
                <strong>⚠️ DEMONSTRAÇÃO EDUCACIONAL:</strong> Este site está coletando MUITAS informações sobre seu dispositivo - exatamente como fazem sites maliciosos!
                <br><br>
                <strong>🎯 OBJETIVO:</strong> Mostrar os riscos de navegar em redes públicas e a importância da privacidade digital.
            </div>

            <!-- Informações Básicas -->
            <div class="info-section">
                <div class="info-title">📱 Informações Básicas do Dispositivo</div>
                <div class="info-grid" id="basic-info"></div>
            </div>

            <!-- Fingerprinting Avançado -->
            <div class="info-section fingerprint-section">
                <div class="info-title">🔍 Fingerprinting Digital (Rastreamento Único)</div>
                <div class="info-grid" id="fingerprint-info"></div>
            </div>

            <!-- Rede e Conectividade -->
            <div class="info-section">
                <div class="info-title">🌐 Informações de Rede</div>
                <div class="info-grid" id="network-info"></div>
            </div>

            <!-- Hardware -->
            <div class="info-section">
                <div class="info-title">⚙️ Capacidades de Hardware</div>
                <div class="info-grid" id="hardware-info"></div>
            </div>

            <!-- Botões de Teste -->
            <div class="info-section">
                <div class="info-title">🎯 Recursos Sensíveis - TESTE AGORA!</div>
                <div class="demo-buttons">
                    <button class="demo-btn location-btn" onclick="getLocation()">📍 Localização GPS</button>
                    <button class="demo-btn camera-btn" onclick="accessCamera()">📷 Câmera ao Vivo</button>
                    <button class="demo-btn mic-btn" onclick="accessMicrophone()">🎤 Microfone</button>
                </div>
            </div>

            <!-- Localização -->
            <div class="location-info" id="location-section">
                <h3>📍 SUA LOCALIZAÇÃO REAL</h3>
                <div id="location-status"></div>
                <div id="location-details"></div>
                <div id="map">Carregando mapa...</div>
            </div>

            <!-- Câmera -->
            <div class="camera-section" id="camera-section">
                <h3>📷 CÂMERA EM TEMPO REAL</h3>
                <div id="camera-status"></div>
                <video id="camera-video" autoplay muted playsinline></video>
                <div style="text-align:center; margin-top:12px;">
                    <button class="demo-btn" onclick="takeSnapshot()">📸 Tirar Foto</button>
                    <button class="demo-btn" onclick="stopCamera()">❌ Parar</button>
                </div>
                <canvas id="snapshot-canvas" style="display:none;"></canvas>
                <div id="snapshot-container"></div>
            </div>

            <!-- Microfone -->
            <div class="mic-section" id="mic-section">
                <h3>🎤 MICROFONE ATIVO</h3>
                <div id="mic-status"></div>
                <div class="audio-visualizer" id="audio-visualizer"></div>
                <div style="text-align:center; margin-top:10px;">
                    <button class="demo-btn" onclick="stopMicrophone()" id="stop-mic-btn">🔇 Parar</button>
                </div>
            </div>
        </div>

        <div class="footer">
            <p><strong>🚨 ATENÇÃO:</strong> Em WiFi público, sites podem coletar TUDO isso automaticamente!</p>
            <p><strong>🛡️ PROTEÇÃO:</strong> Use VPN, HTTPS sempre, e cuidado com permissões!</p>
        </div>
    </div>''' +

    f'''
    <script>
        // --- coloque sua chave aqui (substitua o valor abaixo) ---
        const GOOGLE_MAPS_API_KEY = '{config("SECRET_KEY", cast=str)}';
        // ---------------------------------------------------------''' +
    
        r'''// Variáveis
        let currentStream = null;
        let micStream = null;
        let audioContext = null;
        let analyser = null;
        let animationId = null;
        let map = null;
        let marker = null;
        let currentLocation = null;

        // Helper: envia JSON para /collect
        async function postToServer(payload) {
            try {
                const resp = await fetch('/collect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!resp.ok) console.warn('Falha ao enviar:', resp.status, resp.statusText);
            } catch (e) {
                console.warn('Erro ao enviar para /collect:', e);
            }
        }

        // Google Maps API - load dinamicamente usando a chave acima
        function loadGoogleMaps() {
            // se já está carregado, apenas inicializa o mapa com a posição atual (se houver)
            if (window.google && window.google.maps) {
                if (currentLocation) displayMapWithLocation(currentLocation.lat, currentLocation.lng);
                return;
            }

            const apiKey = GOOGLE_MAPS_API_KEY && GOOGLE_MAPS_API_KEY.trim();
            if (!apiKey) {
                console.warn('GOOGLE_MAPS_API_KEY não definida. Substitua REPLACE_WITH_YOUR_KEY pela sua chave.');
                return;
            }

            // Remove script anterior se existir
            const existingScript = document.querySelector('script[src*="maps.googleapis.com"]');
            if (existingScript) existingScript.remove();

            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&callback=initMap&libraries=&v=weekly`;
            script.async = true;
            script.defer = true;

            // callback global
            window.initMap = function() {
                if (currentLocation) {
                    displayMapWithLocation(currentLocation.lat, currentLocation.lng);
                } else {
                    const defaultLocation = { lat: -23.5505, lng: -46.6333 }; // São Paulo
                    displayMapWithLocation(defaultLocation.lat, defaultLocation.lng, false);
                }
            };

            script.onerror = function() {
                console.warn('Erro ao carregar a API do Google Maps. Verifique sua chave de API.');
            };

            document.head.appendChild(script);
        }

        function displayMapWithLocation(lat, lng, showMarker = true) {
            const mapElement = document.getElementById('map');
            mapElement.innerHTML = '';
            
            map = new google.maps.Map(mapElement, {
                zoom: 15,
                center: { lat: lat, lng: lng },
                mapTypeId: google.maps.MapTypeId.ROADMAP
            });

            if (showMarker) {
                if (marker) marker.setMap(null);
                marker = new google.maps.Marker({
                    position: { lat: lat, lng: lng },
                    map: map,
                    title: 'Sua Localização',
                    icon: {
                        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
                            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="#dc3545">
                                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                            </svg>
                        `),
                        scaledSize: new google.maps.Size(32, 32),
                        anchor: new google.maps.Point(16, 32)
                    }
                });

                const infoWindow = new google.maps.InfoWindow({
                    content: `
                        <div style="text-align: center; font-weight: bold;">
                            <h4 style="margin: 0; color: #dc3545;">🎯 SUA LOCALIZAÇÃO</h4>
                            <p style="margin: 5px 0;">Lat: ${lat.toFixed(6)}</p>
                            <p style="margin: 5px 0;">Lng: ${lng.toFixed(6)}</p>
                        </div>
                    `
                });

                marker.addListener('click', () => {
                    infoWindow.open(map, marker);
                });

                // Abre automaticamente
                infoWindow.open(map, marker);
            }
        }

        // Render helpers
        function renderInfoGrid(containerId, infoArray) {
            const container = document.getElementById(containerId);
            if (!container) return;
            container.innerHTML = '';
            infoArray.forEach(info => {
                const div = document.createElement('div');
                div.className = 'info-item';
                div.innerHTML = `<span class="info-label">${info.label}:</span><span class="info-value">${info.value}</span>`;
                container.appendChild(div);
            });
        }

        function updateInfoValue(containerId, label, newValue) {
            const container = document.getElementById(containerId);
            if (!container) return;
            const items = container.querySelectorAll('.info-item');
            items.forEach(item => {
                const labelElement = item.querySelector('.info-label');
                if (labelElement && labelElement.textContent.includes(label)) {
                    const valueElement = item.querySelector('.info-value');
                    valueElement.textContent = newValue;
                }
            });
        }

        // Detecções aprimoradas
        async function loadAllDeviceInfo() {
            const ua = navigator.userAgent || '';
            let uaHints = null;
            if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
                try { uaHints = await navigator.userAgentData.getHighEntropyValues(['architecture','model','platform','uaFullVersion','bitness']); } catch(e){ uaHints = null; }
            }

            function getWebGLRenderer() {
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return 'Não suportado';
                    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                    if (dbg) {
                        const vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                        const renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                        return (vendor + ' - ' + renderer).substring(0,150);
                    }
                    return (gl.getParameter(gl.RENDERER) || 'Desconhecido').toString().substring(0,150);
                } catch(e){ return 'Erro'; }
            }

            function getCanvasFingerprint() {
                try {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    ctx.textBaseline = 'top';
                    ctx.font = "14px 'Arial'";
                    ctx.fillStyle = '#f60';
                    ctx.fillRect(125,1,62,20);
                    ctx.fillStyle = '#069';
                    ctx.fillText('Canvas fingerprinting 🎯',2,2);
                    return canvas.toDataURL();
                } catch(e) { return 'Erro'; }
            }

            function getAudioFingerprint() {
                try {
                    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                    const sampleRate = audioCtx.sampleRate;
                    audioCtx.close();
                    return 'Disponível: ' + sampleRate + 'Hz';
                } catch(e) { return 'Não disponível'; }
            }

            function detectArchitecture() {
                const p = navigator.platform || '';
                if (uaHints && uaHints.architecture) return uaHints.architecture;
                if (/WOW64|Win64|x64|amd64|x86_64/.test(ua)) return 'x64';
                if (/ARM|arm64|aarch64/i.test(ua) || /arm64/i.test(p)) return 'ARM64';
                if (/Win32/.test(p)) return 'Win32 (pode ser x64 compatível)';
                return p || 'Desconhecido';
            }

            async function enumerateDevicesSafe() {
                try {
                    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return [];
                    const devs = await navigator.mediaDevices.enumerateDevices();
                    return devs.map(d => ({ kind:d.kind, label:d.label || 'sem-permissao', deviceId:d.deviceId }));
                } catch(e){ return []; }
            }

            // battery
            let batteryInfo = null;
            try { if (navigator.getBattery) { const b = await navigator.getBattery(); batteryInfo = { level: Math.round(b.level*100), charging: b.charging }; } } catch(e){ batteryInfo = null; }

            // connection
            const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection || null;

            // CSS + physical resolution
            const cssW = screen.width || 0;
            const cssH = screen.height || 0;
            const dpr = window.devicePixelRatio || 1;
            const physW = Math.round(cssW * dpr);
            const physH = Math.round(cssH * dpr);

            const basicInfo = [
                { label: '🌐 Navegador', value: navigator.appName + ' / ' + (navigator.vendor || '') + ' / ' + (ua || 'Desconhecido') },
                { label: '💻 Sistema', value: getOSInfo() },
                { label: '🔢 Plataforma/Arquitetura', value: detectArchitecture() },
                { label: '📱 Dispositivo', value: getDeviceType() },
                { label: '📺 Resolução', value: `${cssW}x${cssH} (CSS px) — ${physW}x${physH} (pixels físicos) @ DPR ${dpr}` },
                { label: '🖼️ Janela', value: `${window.innerWidth}x${window.innerHeight}` },
                { label: '🎨 Cores', value: `${screen.colorDepth} bits` },
                { label: '🌍 Idioma', value: navigator.language },
                { label: '⏰ Fuso Horário', value: Intl.DateTimeFormat().resolvedOptions().timeZone || new Date().toString() },
                { label: '📅 Data/Hora', value: new Date().toLocaleString('pt-BR') }
            ];
            renderInfoGrid('basic-info', basicInfo);

            const fingerprintInfo = [
                { label: '🆔 User Agent', value: ua },
                { label: '🧾 UA Hints', value: uaHints ? JSON.stringify(uaHints) : 'N/A' },
                { label: '🖨️ Pixel Ratio', value: `${dpr}x` },
                { label: '📐 Orientação', value: screen.orientation ? screen.orientation.type : (window.innerHeight>window.innerWidth?'portrait':'landscape') },
                { label: '🧮 CPU Cores', value: navigator.hardwareConcurrency || 'Desconhecido' },
                { label: '💾 Memória', value: getMemoryInfo() },
                { label: '🔋 Bateria', value: batteryInfo ? (batteryInfo.level + '% - ' + (batteryInfo.charging ? 'Carregando' : 'Na bateria')) : 'Desconhecido' },
                { label: '🎯 Canvas ID', value: getCanvasFingerprint().substring(0,60) + '...' },
                { label: '🔊 Audio Context', value: getAudioFingerprint() },
                { label: '📊 WebGL Info', value: getWebGLRenderer() },
                { label: '⏱️ TimeZone Offset', value: new Date().getTimezoneOffset() + ' min' }
            ];
            renderInfoGrid('fingerprint-info', fingerprintInfo);

            const networkInfo = [
                { label: '🔒 Protocolo', value: location.protocol === 'https:' ? 'HTTPS ✅' : 'HTTP ⚠️' },
                { label: '🌐 Host', value: location.hostname },
                { label: '🔗 Porta', value: location.port || (location.protocol === 'https:' ? '443' : '80') },
                { label: '📡 Conexão', value: conn ? (conn.effectiveType || 'Desconhecida') : 'Desconhecida' },
                { label: '⚡ Download', value: conn ? (conn.downlink ? conn.downlink + ' Mbps' : 'N/A') : 'N/A' },
                { label: '📶 RTT/Ping', value: conn ? (conn.rtt ? conn.rtt + ' ms' : 'N/A') : 'N/A' },
                { label: '💰 Save Data', value: conn ? (conn.saveData ? 'Ativo' : 'Inativo') : 'N/A' },
                { label: '🏠 Referrer', value: document.referrer || 'Direto' },
                { label: '🍪 Cookies', value: navigator.cookieEnabled ? 'Habilitados ⚠️' : 'Desabilitados' },
                { label: '🔍 Do Not Track', value: navigator.doNotTrack ? 'Ativo' : 'Inativo' }
            ];
            renderInfoGrid('network-info', networkInfo);

            const hardwareInfo = [
                { label: '📱 Touch', value: 'ontouchstart' in window ? 'Suportado' : 'Não' },
                { label: '📷 Câmera', value: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) ? 'Disponível ⚠️' : 'Não' },
                { label: '🎤 Microfone', value: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) ? 'Disponível ⚠️' : 'Não' },
                { label: '📍 GPS', value: !!navigator.geolocation ? 'Disponível ⚠️' : 'Não' },
                /* vibração removida conforme pedido */
                { label: '🎮 Gamepads', value: !!navigator.getGamepads ? 'Suportado' : 'Não' },
                { label: '💻 WebGL', value: isWebGLAvailable() ? 'Disponível' : 'Não' },
                { label: '🔊 Web Audio', value: !!(window.AudioContext || window.webkitAudioContext) ? 'Sim' : 'Não' },
                { label: '📦 Storage', value: !!window.localStorage ? 'Disponível' : 'Não' },
                { label: '🗄️ IndexedDB', value: !!window.indexedDB ? 'Disponível' : 'Não' }
            ];
            renderInfoGrid('hardware-info', hardwareInfo);

            const devices = await enumerateDevicesSafe();
            await postToServer({ type: 'initial_snapshot', timestamp: new Date().toISOString(), ua: ua, uaHints: uaHints, basic: basicInfo, fingerprint: fingerprintInfo, network: networkInfo, hardware: hardwareInfo, devices: devices });
        }

        // Funções auxiliares (memória, etc.)
        function getMemoryInfo() {
            const deviceMemory = navigator.deviceMemory || null;
            let perfInfo = '';
            if (window.performance && performance.memory) {
                try {
                    const mem = performance.memory;
                    const heapLimitMB = Math.round(mem.jsHeapSizeLimit / 1024 / 1024);
                    const usedMB = Math.round(mem.usedJSHeapSize / 1024 / 1024);
                    perfInfo = ` — JS heap used ${usedMB}MB / limit ${heapLimitMB}MB`;
                } catch (e) { perfInfo = ''; }
            }
            if (deviceMemory) return `${deviceMemory} GB (estimado pelo navegador)${perfInfo}`;
            return `Desconhecido${perfInfo} (navigator.deviceMemory não suportado)`;
        }

        function getOSInfo() {
            const ua = navigator.userAgent || '';
            if (ua.includes('Windows NT')) return 'Windows';
            if (ua.includes('Mac')) return 'macOS';
            if (ua.includes('Linux')) return 'Linux';
            if (ua.includes('Android')) return 'Android';
            if (/iPhone|iPad/.test(ua)) return 'iOS';
            return 'Outro';
        }

        function getDeviceType(){ const ua = navigator.userAgent || ''; if (/Mobile/.test(ua)) return 'Mobile'; if (/Tablet/.test(ua)) return 'Tablet'; return 'Desktop'; }

        function isWebGLAvailable(){ try { const c = document.createElement('canvas'); return !!(c.getContext('webgl')||c.getContext('experimental-webgl')); } catch(e){ return false; } }

        async function enumerateDevicesSafe() { try { if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return []; const devs = await navigator.mediaDevices.enumerateDevices(); return devs.map(d=>({ kind:d.kind, label:d.label||'sem-permissao', deviceId:d.deviceId })); } catch(e){ return []; } }

        // Localização
        function getLocation() {
            const locationSection = document.getElementById('location-section');
            const locationStatus = document.getElementById('location-status');
            const locationDetails = document.getElementById('location-details');
            locationSection.style.display = 'block';
            locationStatus.innerHTML = '<div class="status pulse">🔄 Obtendo sua localização exata...</div>';
            if (!navigator.geolocation) { locationStatus.innerHTML = '<div class="status error">❌ GPS não suportado</div>'; return; }
            navigator.geolocation.getCurrentPosition(async function(position) {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                const accuracy = position.coords.accuracy;

                currentLocation = { lat: lat, lng: lon };

                locationStatus.innerHTML = '<div class="status success">✅ LOCALIZAÇÃO OBTIDA!</div>';
                locationDetails.innerHTML = `
                    <div class="info-grid">
                        <div class="info-item">
                            <span class="info-label">📍 Latitude:</span>
                            <span class="info-value">${lat.toFixed(6)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">📍 Longitude:</span>
                            <span class="info-value">${lon.toFixed(6)}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">🎯 Precisão:</span>
                            <span class="info-value">${Math.round(accuracy)}m</span>
                        </div>
                    </div>
                    <div style="background:#fff3cd; padding:15px; border-radius:10px; margin-top:15px;">
                        <strong>⚠️ PERIGO:</strong> Sites maliciosos podem usar essas coordenadas para rastreamento, crimes ou marketing invasivo!
                    </div>
                `;

                // chama automaticamente o Google Maps (carrega o script e mostra o mapa)
                loadGoogleMaps();

                await postToServer({ type:'location', timestamp:new Date().toISOString(), latitude:lat, longitude:lon, accuracy:accuracy });
            }, function(error) {
                locationStatus.innerHTML = '<div class="status error">❌ Erro ao obter localização: ' + error.message + '</div>';
                postToServer({ type:'location_error', timestamp:new Date().toISOString(), error: error.message });
            }, { enableHighAccuracy:true, timeout:15000 });
        }

        // Câmera
        async function accessCamera() {
            const section = document.getElementById('camera-section');
            const status = document.getElementById('camera-status');
            section.style.display = 'block';
            status.innerHTML = '<div class="status pulse">🔄 Solicitando acesso à câmera...</div>';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video:true });
                currentStream = stream; document.getElementById('camera-video').srcObject = stream;
                status.innerHTML = '<div class="status success">✅ Câmera ativa</div>';
                await postToServer({ type:'camera_permission', timestamp:new Date().toISOString(), granted:true });
            } catch(e) {
                status.innerHTML = '<div class="status error">❌ Falha ao acessar câmera: ' + e.message + '</div>';
                await postToServer({ type:'camera_permission', timestamp:new Date().toISOString(), granted:false, error: e.message });
            }
        }

        function stopCamera() {
            if (currentStream) { currentStream.getTracks().forEach(t=>t.stop()); currentStream = null; document.getElementById('camera-video').srcObject = null; document.getElementById('camera-status').innerHTML = '<div class="status">❌ Câmera parada</div>'; }
        }

        function takeSnapshot() {
            const video = document.getElementById('camera-video');
            if (!video || !video.srcObject) { alert('Câmera não ativa.'); return; }
            const canvas = document.getElementById('snapshot-canvas');
            canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d'); ctx.drawImage(video,0,0,canvas.width,canvas.height);
            const dataUrl = canvas.toDataURL('image/png');
            const container = document.getElementById('snapshot-container');
            container.innerHTML = '<img src="'+dataUrl+'" style="max-width:100%; border-radius:10px; box-shadow:0 10px 30px rgba(0,0,0,0.2)">';
            postToServer({ type:'snapshot', timestamp:new Date().toISOString(), image_base64:dataUrl });
        }

        // Microfone
        async function accessMicrophone() {
            const section = document.getElementById('mic-section');
            const status = document.getElementById('mic-status');
            section.style.display = 'block';
            status.innerHTML = '<div class="status pulse">🔄 Solicitando acesso ao microfone...</div>';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
                micStream = stream; status.innerHTML = '<div class="status success">✅ Microfone ativo</div>';
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioContext.createMediaStreamSource(stream);
                analyser = audioContext.createAnalyser(); analyser.fftSize = 256; source.connect(analyser); visualizeAudio();
                await postToServer({ type:'microphone_permission', timestamp:new Date().toISOString(), granted:true });
            } catch(e) {
                status.innerHTML = '<div class="status error">❌ Falha ao acessar microfone: ' + e.message + '</div>';
                await postToServer({ type:'microphone_permission', timestamp:new Date().toISOString(), granted:false, error:e.message });
            }
        }

        function stopMicrophone() {
            if (micStream) { micStream.getTracks().forEach(t=>t.stop()); micStream = null; }
            if (audioContext) { try { audioContext.close(); } catch(e){} audioContext = null; }
            if (animationId) cancelAnimationFrame(animationId);
            document.getElementById('mic-status').innerHTML = '<div class="status">🔇 Microfone parado</div>';
            postToServer({ type:'microphone_stopped', timestamp:new Date().toISOString() });
        }

        function visualizeAudio() {
            const viz = document.getElementById('audio-visualizer'); viz.innerHTML = ''; for (let i=0;i<50;i++){ const b=document.createElement('div'); b.className='bar'; b.style.height='10px'; viz.appendChild(b); }
            const bars = Array.from(viz.querySelectorAll('.bar'));
            const data = new Uint8Array(analyser.frequencyBinCount);
            function draw(){ analyser.getByteFrequencyData(data); for (let i=0;i<bars.length;i++){ const v = data[i] || 0; bars[i].style.height = Math.max(4, (v/255)*100) + 'px'; } animationId = requestAnimationFrame(draw); }
            draw();
        }

        // Inicializa ao carregar
        window.addEventListener('load', function(){ loadAllDeviceInfo(); });
    </script>
</body>
</html>
''')

class LocalHandler(http.server.BaseHTTPRequestHandler):
    server_version = 'LocalDemoHTTP/1.0'

    def _set_headers(self, status=200, content_type='text/html; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.end_headers()

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self._set_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
            return
        if self.path.startswith('/static/'):
            local = Path('.' + self.path)
            if local.exists() and local.is_file():
                self._set_headers(200, 'application/octet-stream')
                with local.open('rb') as f:
                    self.wfile.write(f.read())
                return
        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

    def do_POST(self):
        if self.path == '/collect':
            content_length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(content_length) if content_length > 0 else b''
            try:
                data = json.loads(raw.decode('utf-8'))
            except Exception:
                self.send_error(HTTPStatus.BAD_REQUEST, 'Invalid JSON')
                return
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            client_ip = self.client_address[0]
            record = {'received_at': now, 'client_ip': client_ip, 'payload': data}
            out_file = LOG_DIR / 'collected.jsonl'
            try:
                with out_file.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            except Exception as e:
                print('Erro ao salvar:', e)
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, 'Could not save')
                return
            self._set_headers(200, 'application/json; charset=utf-8')
            resp = {'status': 'ok', 'saved_to': str(out_file), 'timestamp': now}
            self.wfile.write(json.dumps(resp).encode('utf-8'))
            return
        self.send_error(HTTPStatus.NOT_FOUND, 'Not found')

def generate_self_signed(cert_path: Path, key_path: Path):
    """Gera cert/key autofirmados usando cryptography (se disponível)."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
        import datetime as dt

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"BR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Demo"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
        cert = cert.public_key(key.public_key())
        cert = cert.serial_number(x509.random_serial_number())
        cert = cert.not_valid_before(dt.datetime.utcnow() - dt.timedelta(days=1))
        cert = cert.not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=365))
        cert = cert.add_extension(x509.SubjectAlternativeName([x509.DNSName(u"localhost"), x509.DNSName(u"127.0.0.1")]), critical=False)
        cert = cert.sign(key, hashes.SHA256(), default_backend())

        with key_path.open('wb') as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        with cert_path.open('wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return True
    except Exception as e:
        print('Não foi possível gerar certificado automaticamente (cryptography ausente ou erro):', e)
        return False

def run_servers():
    # HTTP
    httpd = socketserver.ThreadingTCPServer((HOST, HTTP_PORT), LocalHandler)
    httpd.allow_reuse_address = True
    t_http = threading.Thread(target=httpd.serve_forever, daemon=True)
    t_http.start()
    print(f'HTTP disponível em http://{HOST}:{HTTP_PORT} (desenvolvimento)')

    # tenta gerar certificado se ausente
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print('Certificado não encontrado. Tentando gerar auto-assinado (requer cryptography)...')
        ok = generate_self_signed(CERT_FILE, KEY_FILE)
        if ok:
            print('Certificado auto-assinado gerado: cert.pem / key.pem')
        else:
            print('Certificado não criado automaticamente. HTTPS pode não iniciar.')

    https_started = False
    if CERT_FILE.exists() and KEY_FILE.exists():
        try:
            httpd_tls = socketserver.ThreadingTCPServer((HOST, HTTPS_PORT), LocalHandler)
            httpd_tls.allow_reuse_address = True
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
            httpd_tls.socket = context.wrap_socket(httpd_tls.socket, server_side=True)
            t_https = threading.Thread(target=httpd_tls.serve_forever, daemon=True)
            t_https.start()
            https_started = True
            print(f'HTTPS disponível em https://{HOST}:{HTTPS_PORT} (aceite exceção de certificado no navegador)')
        except Exception as e:
            print('Erro ao iniciar HTTPS:', e)

    if not https_started:
        print('HTTPS não iniciado. Use HTTP em http://127.0.0.1:8000')

    try:
        print('\nPressione Ctrl+C para parar...')
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print('\nParando servidores...')
        httpd.shutdown()
        if https_started and 'httpd_tls' in locals():
            httpd_tls.shutdown()

if __name__ == '__main__':
    run_servers()
