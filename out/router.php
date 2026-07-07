<?php
$uri = urldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));

// If the requested file exists, serve it directly
if ($uri !== '/' && file_exists(__DIR__ . $uri)) {
    return false;
}

// Try appending .html
$htmlPath = __DIR__ . $uri . '.html';
if (file_exists($htmlPath)) {
    header('Content-Type: text/html; charset=utf-8');
    readfile($htmlPath);
    return true;
}

// Fallback to index.html for client-side routing
$indexPath = __DIR__ . '/index.html';
if (file_exists($indexPath)) {
    header('Content-Type: text/html; charset=utf-8');
    readfile($indexPath);
    return true;
}

// 404
http_response_code(404);
echo '404 Not Found';
return true;
