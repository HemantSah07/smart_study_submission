(function () {
    'use strict';

    // ── Sidebar: Mobile Drawer ───────────────────────────────────────────────
    function initSidebar() {
        const sidebar  = document.getElementById('appSidebar');
        const overlay  = document.getElementById('sidebarOverlay');
        const toggle   = document.getElementById('sidebarToggle');
        if (!sidebar) return;

        function openSidebar() {
            sidebar.classList.add('open');
            overlay && overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        }

        function closeSidebar() {
            sidebar.classList.remove('open');
            overlay && overlay.classList.remove('show');
            document.body.style.overflow = '';
        }

        // Mobile hamburger toggle
        if (toggle) {
            toggle.addEventListener('click', function () {
                sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
            });
        }

        // Clicking overlay closes drawer
        if (overlay) overlay.addEventListener('click', closeSidebar);

        // Escape key closes drawer
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sidebar.classList.contains('open')) closeSidebar();
        });

        // Auto-close mobile drawer on nav link click
        sidebar.querySelectorAll('.sidebar-link').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth < 992) closeSidebar();
            });
        });
    }

    // ── Sidebar: Desktop Collapse / Expand ──────────────────────────────────
    function initSidebarCollapse() {
        const sidebar     = document.getElementById('appSidebar');
        const collapseBtn = document.getElementById('sidebarCollapseBtn');
        const collapseIcon = document.getElementById('collapseIcon');
        const appMain     = document.getElementById('appMain');
        const toggle      = document.getElementById('sidebarToggle');
        if (!sidebar || !collapseBtn) return;

        var STORAGE_KEY = 'ss_sidebar_collapsed';

        function setCollapsed(collapsed) {
            if (collapsed) {
                sidebar.classList.add('collapsed');
                appMain && appMain.classList.add('sidebar-collapsed');
                collapseIcon && collapseIcon.classList.replace('fa-chevron-left', 'fa-chevron-right');
                collapseBtn.setAttribute('title', 'Expand sidebar');
                collapseBtn.setAttribute('aria-label', 'Expand sidebar');
            } else {
                sidebar.classList.remove('collapsed');
                appMain && appMain.classList.remove('sidebar-collapsed');
                collapseIcon && collapseIcon.classList.replace('fa-chevron-right', 'fa-chevron-left');
                collapseBtn.setAttribute('title', 'Collapse sidebar');
                collapseBtn.setAttribute('aria-label', 'Collapse sidebar');
            }
            try { localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0'); } catch(e) {}
        }

        // Restore from localStorage
        var stored = '0';
        try { stored = localStorage.getItem(STORAGE_KEY) || '0'; } catch(e) {}
        if (stored === '1' && window.innerWidth >= 992) setCollapsed(true);

        collapseBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            setCollapsed(!sidebar.classList.contains('collapsed'));
        });

        // On mobile: show hamburger toggle, hide desktop collapse btn
        function adaptToWidth() {
            if (window.innerWidth < 992) {
                collapseBtn.style.display = 'none';
                toggle && (toggle.style.display = 'flex');
            } else {
                collapseBtn.style.display = 'flex';
                toggle && (toggle.style.display = 'none');
                // Ensure drawer class removed
                sidebar.classList.remove('open');
                var overlay = document.getElementById('sidebarOverlay');
                overlay && overlay.classList.remove('show');
                document.body.style.overflow = '';
            }
        }

        adaptToWidth();
        window.addEventListener('resize', adaptToWidth);
    }

    // ── Hours Slider (Planner) ───────────────────────────────────────────────
    function initHoursSlider() {
        const slider  = document.getElementById('totalHoursSlider');
        const display = document.getElementById('totalHoursDisplay');
        const hidden  = document.getElementById('totalHoursInput');
        if (!slider || !display) return;

        function sync() {
            const val = slider.value;
            display.textContent = val;
            if (hidden) hidden.value = val;
        }
        slider.addEventListener('input', sync);
        sync();
    }

    // ── Planner Form: Loading Overlay with Animated Messages ────────────────
    function initPlannerForm() {
        const form    = document.getElementById('planner-form');
        const loading = document.getElementById('plannerLoading');
        const msgEl   = document.getElementById('plannerLoadingMsg');
        if (!form) return;

        var messages = [
            'Reviewing your academic profile…',
            'Evaluating subject risk levels…',
            'Allocating study hours by priority…',
            'Balancing your weekly workload…',
            'Building your personalized schedule…',
        ];

        form.addEventListener('submit', function () {
            if (loading) {
                loading.classList.add('show');
                // Rotate messages
                var idx = 0;
                if (msgEl) {
                    msgEl.textContent = messages[0];
                    var interval = setInterval(function () {
                        idx = (idx + 1) % messages.length;
                        if (msgEl) msgEl.textContent = messages[idx];
                    }, 1600);
                    // Store to clear if needed
                    loading.dataset.interval = interval;
                }
            }
            var btn = form.querySelector('[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Generating Adaptive Plan…';
            }
        });
    }

    // ── Planner Stepper Progression ──────────────────────────────────────────
    function initPlannerStepper() {
        const steps = document.querySelectorAll('.ss-planner-stepper .ss-stepper-step');
        if (!steps.length) return;

        // Check form elements to update active step
        const presetSelect = document.getElementById('availability-preset-select');
        const generateBtn  = document.getElementById('generate-button-container');

        if (presetSelect) {
            presetSelect.addEventListener('change', function () {
                if (steps[1]) {
                    steps[0].classList.add('completed');
                    steps[1].classList.add('active');
                }
            });
        }

        if (generateBtn) {
            const observer = new MutationObserver(function () {
                if (!generateBtn.classList.contains('d-none')) {
                    if (steps[2]) {
                        steps[1].classList.add('completed');
                        steps[2].classList.add('active');
                    }
                    if (steps[3]) {
                        steps[3].classList.add('active');
                    }
                }
            });
            observer.observe(generateBtn, { attributes: true, attributeFilter: ['class'] });
        }
    }


    // ── Auto-dismiss Alerts ──────────────────────────────────────────────────
    function initAutoDismissAlerts() {
        document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
            setTimeout(function () {
                if (alert.parentNode) {
                    alert.classList.remove('show');
                    setTimeout(function () { if (alert.parentNode) alert.remove(); }, 300);
                }
            }, 6000);
        });
    }

    // ── Upload Dropzone ──────────────────────────────────────────────────────
    function initUploadDropzone() {
        const zone  = document.getElementById('uploadDropzone');
        const input = document.getElementById('documentFileInput');
        const label = document.getElementById('uploadFileName');
        if (!zone || !input) return;

        zone.addEventListener('click', function () { input.click(); });
        zone.addEventListener('dragover', function (e) {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', function () { zone.classList.remove('dragover'); });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                if (label) label.textContent = e.dataTransfer.files[0].name;
            }
        });
        input.addEventListener('change', function () {
            if (label && input.files[0]) label.textContent = input.files[0].name;
        });

        var form = zone.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                var btn     = document.getElementById('uploadBtn');
                var lding   = document.getElementById('uploadLoading');
                if (btn) btn.classList.add('d-none');
                if (lding) lding.classList.remove('d-none');
            });
        }
    }

    // ── Subject Select All ───────────────────────────────────────────────────
    function initSubjectSelectAll() {
        const selectAll = document.getElementById('selectAllSubjects');
        const boxes     = document.querySelectorAll('input[name="subjects"]');
        if (!selectAll || !boxes.length) return;
        selectAll.addEventListener('change', function () {
            boxes.forEach(function (cb) { cb.checked = selectAll.checked; });
        });
    }

    // ── Time-aware Greeting ──────────────────────────────────────────────────
    function initGreeting() {
        var el = document.getElementById('ssGreetingTime');
        if (!el) return;
        var h = new Date().getHours();
        var greeting = h < 12 ? 'Good Morning' : h < 17 ? 'Good Afternoon' : 'Good Evening';
        el.textContent = greeting;
    }

    // ── Profile View/Edit Toggle ─────────────────────────────────────────────
    function initProfileToggle() {
        var editBtn   = document.getElementById('ssProfileEditBtn');
        var cancelBtn = document.getElementById('ssProfileCancelBtn');
        var container = document.getElementById('ssProfileContainer');
        if (!editBtn || !container) return;

        editBtn.addEventListener('click', function () {
            container.classList.add('ss-profile-edit-mode');
            editBtn.style.display = 'none';
        });
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function () {
                container.classList.remove('ss-profile-edit-mode');
                editBtn.style.display = '';
            });
        }
    }

    // ── Scroll-triggered Entrance Animations ────────────────────────────────
    function initScrollAnimations() {
        if (!('IntersectionObserver' in window)) return;
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

        document.querySelectorAll('.card, .stat-card, .hero-banner, .ss-next-action, .feature-card, .ss-benefit-card, .ss-log-entry').forEach(function (el) {
            if (!el.style.animation && !el.classList.contains('no-animate')) {
                el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                observer.observe(el);
            }
        });
    }

    // ── Animated Counters ────────────────────────────────────────────────────
    function initCounters() {
        document.querySelectorAll('.stat-value[data-count]').forEach(function (el) {
            var target = parseFloat(el.getAttribute('data-count'));
            var suffix = el.getAttribute('data-suffix') || '';
            var duration = 1200;
            var start = performance.now();
            function update(now) {
                var progress = Math.min((now - start) / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                el.textContent = (target * eased).toFixed(el.getAttribute('data-decimals') || 0) + suffix;
                if (progress < 1) requestAnimationFrame(update);
            }
            requestAnimationFrame(update);
        });
    }

    // ── Page Content Padding ─────────────────────────────────────────────────
    function initPageContent() {
        // Wrap app-main content in page-content div if not already wrapped
        var appMain = document.getElementById('appMain');
        if (!appMain) return;
        // Ensure topbar stays sticky at top
        var topbar = appMain.querySelector('.ss-topbar');
        if (topbar && !appMain.querySelector('.page-content')) {
            // Apply consistent padding to block-level siblings of topbar
            var children = Array.from(appMain.children);
            children.forEach(function (child) {
                if (child !== topbar && !child.classList.contains('ss-topbar') && !child.style.padding) {
                    if (!child.style.paddingLeft) child.style.paddingLeft = '';
                }
            });
        }
    }

    // ── Init All ─────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        initSidebar();
        initSidebarCollapse();
        initHoursSlider();
        initPlannerForm();
        initPlannerStepper();
        initAutoDismissAlerts();
        initUploadDropzone();
        initSubjectSelectAll();
        initGreeting();
        initProfileToggle();
        initScrollAnimations();
        initCounters();
        initPageContent();
    });


})();

