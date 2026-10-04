/* ========================================
   SWAP 全局基础脚本（defer 加载，不阻塞渲染）
   ======================================== */

// 全局 CSRF Token 获取函数 - 从 cookie 中获取（Django 官方推荐方式）
function getCSRFToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 'csrftoken'.length + 1) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Toast 提示
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        ${message}
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, duration);
}

// 全局翻译字典
const translations = {
    'zh-CN': {
        'nav.home': '首页',
        'nav.goods': '全部商品',
        'nav.support': '支持我们',
        'nav.advertise': '广告投放',
        'nav.publish': '发布商品',
        'nav.messages': '消息',
        'nav.profile': '个人中心',
        'nav.transactions': '交易信息',
        'nav.favorites': '我的收藏',
        'nav.edit_profile': '编辑资料',
        'nav.settings': '设置',
        'nav.logout': '退出登录',
        'footer.about': '关于我们',
        'footer.privacy': '隐私政策',
        'footer.terms': '用户协议',
        'footer.admin': '后台管理',
        'search.placeholder': '搜索你想要的商品...',
        'publish.btn': '发布商品',
        'settings.title': '设置',
        'settings.shortcuts': '快捷键设置',
        'settings.shortcuts.desc': '启用后可使用快捷键快速跳转',
        'settings.shortcuts.home': '首页',
        'settings.shortcuts.list': '商品列表',
        'settings.shortcuts.publish': '发布商品',
        'settings.notifications': '消息通知',
        'settings.notifications.desc': '接收新消息和交易提醒',
        'settings.language': '语言设置',
        'settings.language.desc': '选择网站显示语言',
        'settings.password': '修改密码',
        'settings.password.old': '当前密码',
        'settings.password.new': '新密码',
        'settings.password.confirm': '确认新密码',
        'settings.password.submit': '保存新密码',
        'settings.password.ok': '密码修改成功',
        'settings.password.err.old': '请输入当前密码',
        'settings.password.err.short': '新密码至少6位',
        'settings.password.err.mismatch': '两次输入的新密码不一致',
        'settings.password.err.same': '新密码不能与当前密码相同',
        'settings.password.err.fail': '密码修改失败，请重试',
        'settings.password.err.network': '网络异常，请重试',
        'settings.cache': '本地缓存',
        'settings.cache.clear': '清除本地缓存',
        'settings.cache.desc': '清除聊天记录等本地缓存数据，不影响登录状态',
        'settings.cache.button': '清除缓存',
        'settings.cache.confirm.title': '清除本地缓存',
        'settings.cache.confirm.text': '将删除本机保存的聊天记录等缓存数据，且无法恢复。确定继续吗？',
        'settings.cache.cleared': '本地缓存已清除',
        'settings.cache.cancel': '取消',
        'settings.cache.ok': '确定',
        'toast.shortcuts.enabled': '快捷键已启用',
        'toast.shortcuts.disabled': '快捷键已禁用',
        'toast.notifications.enabled': '浏览器通知已启用',
        'toast.notifications.disabled': '浏览器通知已禁用',
        'toast.notifications.permission': '请允许通知权限',
        'toast.notifications.failed': '通知权限请求失败',
        'toast.language.saved': '语言设置已保存，页面即将刷新'
    },
    'en-US': {
        'nav.home': 'Home',
        'nav.goods': 'All Goods',
        'nav.support': 'Support Us',
        'nav.advertise': 'Advertise',
        'nav.publish': 'Publish',
        'nav.messages': 'Messages',
        'nav.profile': 'Profile',
        'nav.transactions': 'Transactions',
        'nav.favorites': 'My Favorites',
        'nav.edit_profile': 'Edit Profile',
        'nav.settings': 'Settings',
        'nav.logout': 'Logout',
        'footer.about': 'About Us',
        'footer.privacy': 'Privacy Policy',
        'footer.terms': 'Terms of Service',
        'footer.admin': 'Admin',
        'search.placeholder': 'Search for products...',
        'publish.btn': 'Publish',
        'settings.title': 'Settings',
        'settings.shortcuts': 'Shortcut Settings',
        'settings.shortcuts.desc': 'Enable to use shortcut keys for quick navigation',
        'settings.shortcuts.home': 'Home',
        'settings.shortcuts.list': 'Goods List',
        'settings.shortcuts.publish': 'Publish Goods',
        'settings.notifications': 'Notifications',
        'settings.notifications.desc': 'Receive new messages and transaction reminders',
        'settings.language': 'Language Settings',
        'settings.language.desc': 'Select website display language',
        'settings.password': 'Change Password',
        'settings.password.old': 'Current Password',
        'settings.password.new': 'New Password',
        'settings.password.confirm': 'Confirm New Password',
        'settings.password.submit': 'Save New Password',
        'settings.password.ok': 'Password changed successfully',
        'settings.password.err.old': 'Please enter your current password',
        'settings.password.err.short': 'New password must be at least 6 characters',
        'settings.password.err.mismatch': 'Passwords do not match',
        'settings.password.err.same': 'New password must differ from current password',
        'settings.password.err.fail': 'Failed to change password, please retry',
        'settings.password.err.network': 'Network error, please retry',
        'settings.cache': 'Local Cache',
        'settings.cache.clear': 'Clear Local Cache',
        'settings.cache.desc': 'Clear locally cached data such as chat history. Login state is not affected',
        'settings.cache.button': 'Clear Cache',
        'settings.cache.confirm.title': 'Clear Local Cache',
        'settings.cache.confirm.text': 'This will delete locally cached data such as chat history. This cannot be undone. Continue?',
        'settings.cache.cleared': 'Local cache cleared',
        'settings.cache.cancel': 'Cancel',
        'settings.cache.ok': 'OK',
        'toast.shortcuts.enabled': 'Shortcuts enabled',
        'toast.shortcuts.disabled': 'Shortcuts disabled',
        'toast.notifications.enabled': 'Browser notifications enabled',
        'toast.notifications.disabled': 'Browser notifications disabled',
        'toast.notifications.permission': 'Please allow notification permission',
        'toast.notifications.failed': 'Notification permission request failed',
        'toast.language.saved': 'Language settings saved, page will refresh'
    }
};

// 全局翻译函数
function translatePage(lang) {
    // 翻译导航
    const navElements = document.querySelectorAll('[data-i18n]');
    navElements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            el.textContent = translations[lang][key];
        }
    });

    // 翻译占位文本
    const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
    placeholderElements.forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (translations[lang] && translations[lang][key]) {
            el.placeholder = translations[lang][key];
        }
    });

    // 翻译搜索框
    const searchInput = document.getElementById('searchInput');
    if (searchInput && translations[lang] && translations[lang]['search.placeholder']) {
        searchInput.placeholder = translations[lang]['search.placeholder'];
    }

    // 翻译发布按钮
    const publishBtn = document.getElementById('publishBtn');
    if (publishBtn && translations[lang] && translations[lang]['publish.btn']) {
        publishBtn.textContent = translations[lang]['publish.btn'];
    }
}

// 全局初始化语言
function initGlobalLanguage() {
    const currentLang = localStorage.getItem('language') || 'zh-CN';
    translatePage(currentLang);

    // 更新页面标题
    if (translations[currentLang] && translations[currentLang]['page.title']) {
        document.title = translations[currentLang]['page.title'];
    }
}

// 模态框通用处理
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal-mask.show');
        modals.forEach(modal => {
            modal.classList.remove('show');
        });
    }
});

// trapped焦点在模态框内
function trapModalFocus(modal) {
    const focusableElements = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    modal.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            if (e.shiftKey && document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            } else if (!e.shiftKey && document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    });
}

// 页面加载完成后执行全局初始化
document.addEventListener('DOMContentLoaded', function() {
    initGlobalLanguage();

    // 渲染 Django messages（由模板注入 window.__djangoMessages）
    if (window.__djangoMessages && window.__djangoMessages.length) {
        window.__djangoMessages.forEach(function(m) {
            showToast(m.text, m.tag);
        });
    }

    // 移动端下拉菜单点击触发
    const userDropdown = document.querySelector('.user-dropdown');
    if (userDropdown) {
        const userAvatar = userDropdown.querySelector('.user-avatar');
        const dropdownMenu = userDropdown.querySelector('.dropdown-menu');

        userAvatar.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdownMenu.classList.toggle('show');
        });

        // 点击页面其他地方关闭下拉菜单
        document.addEventListener('click', function() {
            dropdownMenu.classList.remove('show');
        });

        // 阻止下拉菜单内部点击冒泡
        dropdownMenu.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }

    // 未读消息徽章逻辑（显示具体未读数字）
    window.updateUnreadBadge = function(count = 0) {
        const badge = document.getElementById('messageUnreadBadge');
        if (!badge) return false;
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'block';
        } else {
            badge.textContent = '';
            badge.style.display = 'none';
        }
        return true;
    };

    // 全站未读轮询：3秒一次，多设备已读状态通过服务端数据同步
    (function pollUnread() {
        if (!document.getElementById('messageUnreadBadge')) return; // 未登录不轮询

        let stopped = false;
        async function tick() {
            if (stopped) return;
            try {
                const res = await fetch('/chat/api/unread/', { headers: { 'X-Requested-With': 'fetch' } });
                if (res.status === 401 || res.status === 403) { stopped = true; return; }
                const data = await res.json();
                if (data.success) {
                    if (!window.updateUnreadBadge(data.count || 0)) { stopped = true; return; }
                    // 通知会话列表页刷新数字徽章
                    document.querySelectorAll('[data-conv-id]').forEach(function(item) {
                        const n = (data.conversations || {})[item.dataset.convId] || 0;
                        const num = item.querySelector('.conv-badge');
                        if (num) {
                            num.textContent = n;
                            num.style.display = n > 0 ? 'flex' : 'none';
                        }
                    });
                }
            } catch (e) { /* 网络异常忽略，下轮重试 */ }
            if (!stopped) setTimeout(tick, 2000);
        }
        tick();
    })();
});

// 移动端抽屉菜单
(function() {
    function initMobileNav() {
        const toggle = document.getElementById('navbarToggle');
        const nav = document.getElementById('mobileNav');
        const mask = document.getElementById('mobileNavMask');
        const closeBtn = document.getElementById('mobileNavClose');
        if (!toggle || !nav || !mask || !closeBtn) return;

        function openNav() {
            nav.classList.add('show');
            mask.classList.add('show');
            document.body.classList.add('mobile-nav-open');
            toggle.classList.add('active');
            toggle.setAttribute('aria-expanded', 'true');
            nav.setAttribute('aria-hidden', 'false');
        }
        function closeNav() {
            nav.classList.remove('show');
            mask.classList.remove('show');
            document.body.classList.remove('mobile-nav-open');
            toggle.classList.remove('active');
            toggle.setAttribute('aria-expanded', 'false');
            nav.setAttribute('aria-hidden', 'true');
        }

        toggle.addEventListener('click', function(e) {
            e.stopPropagation();
            if (nav.classList.contains('show')) { closeNav(); } else { openNav(); }
        });
        mask.addEventListener('click', closeNav);
        closeBtn.addEventListener('click', closeNav);
        nav.querySelectorAll('.mobile-nav-links a').forEach(function(a) {
            a.addEventListener('click', closeNav);
        });
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) closeNav();
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMobileNav);
    } else {
        initMobileNav();
    }
})();
