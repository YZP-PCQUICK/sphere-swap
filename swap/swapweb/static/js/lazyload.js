/* ========================================
   SWAP 渐进式资源加载（IntersectionObserver 懒加载 + 骨架屏 + 失败处理）
   兼容：Chrome / Firefox / Safari / Edge / iOS Safari / Android Chrome /
        微信、QQ 内置浏览器（X5/WKWebView）
   ======================================== */
(function () {
    'use strict';

    /* ---------- 1. 懒加载：img[data-src] 进入视口后再加载 ---------- */
    function loadImg(img) {
        var src = img.getAttribute('data-src');
        if (!src) return;
        img.removeAttribute('data-src');
        // 触发加载，load/error 事件由统一监听处理
        img.src = src;
    }

    var lazyImgs = Array.prototype.slice.call(document.querySelectorAll('img[data-src]'));

    if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    loadImg(entry.target);
                    io.unobserve(entry.target);
                }
            });
        }, {
            rootMargin: '200px 0px', // 提前 200px 预加载
            threshold: 0.01
        });
        lazyImgs.forEach(function (img) { io.observe(img); });
    } else {
        // 兜底：不支持 IntersectionObserver 的老浏览器直接加载
        lazyImgs.forEach(loadImg);
    }

    /* ---------- 2. 骨架屏 -> 图片淡入 / 加载失败处理 ---------- */
    function markLoaded(img) {
        img.classList.add('img-loaded');
        var box = img.closest('.goods-card-img, .img-skeleton-box');
        if (box) box.classList.add('img-loaded');
    }

    function markError(img) {
        img.classList.add('img-error');
        var box = img.closest('.goods-card-img, .img-skeleton-box');
        if (box) box.classList.add('img-error');
        // 有备用图则降级加载
        var fallback = img.getAttribute('data-fallback');
        if (fallback && img.src !== fallback) {
            img.classList.remove('img-error');
            img.src = fallback;
            return;
        }
        // 无备用图：显示占位图标（若容器存在）
        if (box && !box.querySelector('.img-placeholder')) {
            var ph = document.createElement('div');
            ph.className = 'img-placeholder';
            ph.innerHTML = '<svg class="icon" style="width:32px;height:32px;"><use href="#icon-image"></use></svg>';
            box.appendChild(ph);
        }
    }

    document.addEventListener('load', function (e) {
        if (e.target && e.target.tagName === 'IMG') markLoaded(e.target);
    }, true); // img 的 load 事件不冒泡，用捕获

    document.addEventListener('error', function (e) {
        if (e.target && e.target.tagName === 'IMG') markError(e.target);
    }, true);

    // 处理脚本执行前已经加载完成的图片（缓存命中等）
    Array.prototype.slice.call(document.images).forEach(function (img) {
        if (img.complete && img.naturalWidth > 0) markLoaded(img);
    });

    /* ---------- 3. 链接预取：桌面端悬停 80ms 后 prefetch，空闲时预取首页资源 ---------- */
    var prefetchCache = {};
    function prefetch(url) {
        if (!url || prefetchCache[url]) return;
        var u = new URL(url, location.href);
        if (u.origin !== location.origin) return; // 仅同源
        // 跳过会产生副作用的页面（如聊天室GET不应被预取）
        if (u.pathname.indexOf('/chat/') === 0) return;
        prefetchCache[url] = true;
        var link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = url;
        document.head.appendChild(link);
    }

    if (window.matchMedia && window.matchMedia('(hover: hover)').matches) {
        var hoverTimer = null;
        document.addEventListener('mouseover', function (e) {
            var a = e.target.closest && e.target.closest('a[href]');
            if (!a) return;
            clearTimeout(hoverTimer);
            hoverTimer = setTimeout(function () { prefetch(a.href); }, 80);
        });
        document.addEventListener('mouseout', function () { clearTimeout(hoverTimer); });
    }

    // 空闲时间预取（不支持 requestIdleCallback 的环境跳过）
    if (window.requestIdleCallback) {
        requestIdleCallback(function () { /* 预留给后续关键列表页预取 */ }, { timeout: 3000 });
    }
})();
