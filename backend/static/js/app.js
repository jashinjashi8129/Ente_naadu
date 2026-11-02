/**
 * Ente Naadu - Modern 3D Interactive & Performance Layer
 * Lightweight, zero-dependency, ultra-fast script
 */

// Early fast-path scroll restoration before DOMContentLoaded
try {
  const _savedRaw = sessionStorage.getItem('ente_naadu_scroll_state');
  if (_savedRaw) {
    const _data = JSON.parse(_savedRaw);
    if (_data && typeof _data.y === 'number' && _data.y > 0 && (Date.now() - _data.timestamp < 30000)) {
      if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
      }
      window.scrollTo(0, _data.y);
    }
  }
} catch (e) {}

document.addEventListener('DOMContentLoaded', () => {
  initScrollPositionPreservation();
  init3DCardTilt();
  initScrollReveal();
  initNumberCounters();
  initMobileMenu();
  initDesktopDropdown();
  initDoubleSubmitPrevention();
  initLocationCascading();
});

/**
 * 1. Subtle 3D Card Tilt System
 * Tracks pointer coordinates relative to card center and applies gentle 3D transform
 */
function init3DCardTilt() {
  // Only apply tilt on devices that support hover and fine pointers (desktops/laptops)
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    return;
  }

  const cards = document.querySelectorAll('.card-3d');

  cards.forEach(card => {
    let bounds;

    function onMouseEnter() {
      bounds = card.getBoundingClientRect();
      document.addEventListener('mousemove', onMouseMove);
    }

    function onMouseMove(e) {
      if (!bounds) bounds = card.getBoundingClientRect();
      const mouseX = e.clientX;
      const mouseY = e.clientY;
      const leftX = mouseX - bounds.x;
      const topY = mouseY - bounds.y;

      // Only calculate if cursor is roughly around the card
      if (leftX < -20 || leftX > bounds.width + 20 || topY < -20 || topY > bounds.height + 20) {
        return;
      }

      const center = {
        x: leftX - bounds.width / 2,
        y: topY - bounds.height / 2
      };

      const distance = Math.sqrt(center.x ** 2 + center.y ** 2);
      const maxDistance = Math.max(bounds.width, bounds.height) / 2;
      const intensity = Math.min(distance / maxDistance, 1);

      // Max tilt angle: 6 degrees (subtle, non-distracting)
      const maxAngle = 6;
      const rotateX = (-center.y / (bounds.height / 2)) * maxAngle;
      const rotateY = (center.x / (bounds.width / 2)) * maxAngle;

      card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-4px)`;
    }

    function onMouseLeave() {
      document.removeEventListener('mousemove', onMouseMove);
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
    }

    card.addEventListener('mouseenter', onMouseEnter);
    card.addEventListener('mouseleave', onMouseLeave);
  });
}

/**
 * 2. Scroll Reveal Animations with IntersectionObserver
 */
function initScrollReveal() {
  const elements = document.querySelectorAll('.reveal-on-scroll');
  if (!elements.length) return;

  if (!('IntersectionObserver' in window)) {
    // Fallback for older browsers
    elements.forEach(el => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        obs.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px'
  });

  elements.forEach(el => observer.observe(el));
}

/**
 * 3. Animated Number Counters (for Live Community Metrics)
 */
function initNumberCounters() {
  const counters = document.querySelectorAll('[data-count]');
  if (!counters.length) return;

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const target = entry.target;
        const targetValue = parseInt(target.getAttribute('data-count'), 10) || 0;
        animateCounter(target, targetValue);
        obs.unobserve(target);
      }
    });
  }, { threshold: 0.2 });

  counters.forEach(counter => observer.observe(counter));
}

function animateCounter(element, targetValue) {
  const duration = 1200; // ms
  const frameRate = 1000 / 60; // 60fps
  const totalFrames = Math.round(duration / frameRate);
  let frame = 0;

  const timer = setInterval(() => {
    frame++;
    // Ease out quad
    const progress = frame / totalFrames;
    const easedProgress = progress * (2 - progress);
    const current = Math.floor(easedProgress * targetValue);

    element.textContent = current.toLocaleString('en-IN');

    if (frame >= totalFrames) {
      element.textContent = targetValue.toLocaleString('en-IN');
      clearInterval(timer);
    }
  }, frameRate);
}

/**
 * 4. Accessible Modal System with Viewport & Scroll Locking
 */
let modalScrollY = 0;
let modalScrollX = 0;

window.closeMobileMenuDrawer = function() {
  const mobileMenu = document.getElementById('mobileMenuDrawer');
  const toggleBtn = document.getElementById('mobileMenuToggle');
  if (mobileMenu) {
    mobileMenu.classList.add('hidden');
  }
  document.body.style.overflow = '';
  if (toggleBtn) {
    toggleBtn.setAttribute('aria-expanded', 'false');
  }
};

window.openModal = function(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;

  // Auto-close mobile navigation drawer if it was open
  window.closeMobileMenuDrawer();

  // Track scroll position before locking body
  modalScrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
  modalScrollX = window.scrollX || window.pageXOffset || document.documentElement.scrollLeft || 0;

  modal.classList.remove('hidden');
  document.body.classList.add('modal-open');
  document.body.style.overflow = 'hidden';

  // Focus first input safely without scrolling viewport
  const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
  if (firstInput) {
    setTimeout(() => {
      try {
        firstInput.focus({ preventScroll: true });
      } catch (err) {
        firstInput.focus();
      }
    }, 50);
  }
};

window.closeModal = function(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.add('hidden');

  // Check if any other modal is still visible before restoring body scroll
  const visibleModals = document.querySelectorAll('[id$="Modal"]:not(.hidden)');
  if (visibleModals.length === 0) {
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    if (typeof modalScrollY === 'number' && modalScrollY > 0) {
      window.scrollTo({ top: modalScrollY, left: modalScrollX, behavior: 'instant' });
    }
  }
};

// Global escape key and outside click handling
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const visibleModals = document.querySelectorAll('[id$="Modal"]:not(.hidden)');
    visibleModals.forEach(m => window.closeModal(m.id));
  }
});

document.addEventListener('click', (e) => {
  if (e.target.hasAttribute('id') && e.target.id.endsWith('Modal') && !e.target.classList.contains('hidden')) {
    window.closeModal(e.target.id);
  }
});

/**
 * 5. Mobile & Tablet Navigation Menu Drawer
 */
function initMobileMenu() {
  const toggleBtn = document.getElementById('mobileMenuToggle');
  const mobileMenu = document.getElementById('mobileMenuDrawer');
  const closeBtn = document.getElementById('closeMobileMenu');
  const backdrop = document.getElementById('mobileMenuBackdrop');

  function openDrawer() {
    if (!mobileMenu) return;
    mobileMenu.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', 'true');
    }
  }

  function closeDrawer() {
    if (!mobileMenu) return;
    mobileMenu.classList.add('hidden');
    document.body.style.overflow = '';
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-expanded', 'false');
    }
  }

  // Auto-close drawer when clicking any link inside it (anchor links or navigation)
  if (mobileMenu) {
    const drawerLinks = mobileMenu.querySelectorAll('a');
    drawerLinks.forEach(link => {
      link.addEventListener('click', () => {
        closeDrawer();
      });
    });
  }

  if (toggleBtn && mobileMenu) {
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (mobileMenu.classList.contains('hidden')) {
        openDrawer();
      } else {
        closeDrawer();
      }
    });
  }

  if (closeBtn && mobileMenu) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      closeDrawer();
    });
  }

  if (backdrop && mobileMenu) {
    backdrop.addEventListener('click', () => {
      closeDrawer();
    });
  }

  // Close when pressing Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mobileMenu && !mobileMenu.classList.contains('hidden')) {
      closeDrawer();
    }
  });

  // Global helper for opening/closing from external modal clicks
  window.closeMobileMenuDrawer = closeDrawer;
}

/**
 * 5b. Desktop "More" (കൂടുതൽ) Dropdown Menu
 */
function initDesktopDropdown() {
  const dropdownBtn = document.getElementById('desktopMoreDropdownBtn');
  const dropdownMenu = document.getElementById('desktopMoreDropdownMenu');
  const chevron = document.getElementById('desktopMoreChevron');
  const container = document.getElementById('desktopMoreDropdownContainer');

  if (!dropdownBtn || !dropdownMenu) return;

  // Global toggle handler
  window.toggleDesktopMoreMenu = function(e) {
    if (e) {
      e.stopPropagation();
      if (e.preventDefault) e.preventDefault();
    }
    const isClosed = dropdownMenu.classList.contains('hidden') || dropdownMenu.style.display === 'none';
    if (isClosed) {
      dropdownMenu.classList.remove('hidden');
      dropdownMenu.style.display = 'block';
      dropdownBtn.setAttribute('aria-expanded', 'true');
      if (chevron) chevron.style.transform = 'rotate(180deg)';
    } else {
      dropdownMenu.classList.add('hidden');
      dropdownMenu.style.display = 'none';
      dropdownBtn.setAttribute('aria-expanded', 'false');
      if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
  };

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (container && !container.contains(e.target)) {
      dropdownMenu.classList.add('hidden');
      dropdownMenu.style.display = 'none';
      dropdownBtn.setAttribute('aria-expanded', 'false');
      if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
  });

  // Close on Escape key
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && dropdownMenu.style.display !== 'none' && !dropdownMenu.classList.contains('hidden')) {
      dropdownMenu.classList.add('hidden');
      dropdownMenu.style.display = 'none';
      dropdownBtn.setAttribute('aria-expanded', 'false');
      if (chevron) chevron.style.transform = 'rotate(0deg)';
    }
  });

  // Close dropdown menu when clicking any link inside it
  const dropdownLinks = dropdownMenu.querySelectorAll('a');
  dropdownLinks.forEach(link => {
    link.addEventListener('click', () => {
      dropdownMenu.classList.add('hidden');
      dropdownMenu.style.display = 'none';
      dropdownBtn.setAttribute('aria-expanded', 'false');
      if (chevron) chevron.style.transform = 'rotate(0deg)';
    });
  });
}

/**
 * 6. Scroll Position Preservation Across Form Submissions & Django Redirects
 * Saves exact scroll position before actions (Delete, Toggle Stock, Status Updates, Filters)
 * and restores it seamlessly on page reload without jumping to the top.
 */
function initScrollPositionPreservation() {
  const SESSION_KEY = 'ente_naadu_scroll_state';

  // 1. Capture scroll coordinates
  function capturePosition(triggerEl) {
    try {
      const scrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
      const scrollX = window.scrollX || window.pageXOffset || document.documentElement.scrollLeft || 0;

      // Only save if user has actually scrolled
      if (scrollY <= 0 && scrollX <= 0) return;

      const payload = {
        y: scrollY,
        x: scrollX,
        path: window.location.pathname,
        timestamp: Date.now()
      };

      sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    } catch (e) {
      // Ignore if sessionStorage is restricted/disabled
    }
  }

  // Capture on form submission (Action buttons, deletes, toggles, status updates)
  document.addEventListener('submit', (e) => {
    const trigger = e.submitter || (e.target && e.target.querySelector ? e.target.querySelector('button[type="submit"]') : null) || e.target;
    capturePosition(trigger);
  }, true);

  // Capture on input/select change (category, ward, status filters, quantity spinners)
  document.addEventListener('change', (e) => {
    if (e.target && (e.target.form || e.target.closest('form'))) {
      capturePosition(e.target);
    }
  }, true);

  // Capture on clicks on buttons / action elements before navigation
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button, input[type="submit"], a[data-preserve-scroll]');
    if (btn) {
      capturePosition(btn);
    }
  }, true);

  // Smooth in-page scrolling for anchor targets on current page without full reload
  document.addEventListener('click', (e) => {
    const anchor = e.target.closest('a[href*="#"]');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (!href || href === '#' || href.startsWith('javascript:')) return;
    const hashIndex = href.indexOf('#');
    if (hashIndex === -1) return;
    const hash = href.substring(hashIndex);
    if (hash.length <= 1) return;

    // If anchor is on current page or root on '/'
    const isRoot = window.location.pathname === '/' || window.location.pathname === '';
    const isAnchorForCurrentPath = href.startsWith(window.location.pathname + '#') || (isRoot && href.startsWith('/#')) || href.startsWith('#');

    if (isAnchorForCurrentPath) {
      try {
        const targetEl = document.querySelector(hash);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
          if (history.pushState) {
            history.pushState(null, null, hash);
          }
        }
      } catch (err) {}
    }
  });

  // Fallback capture before page unloads
  window.addEventListener('beforeunload', () => {
    const scrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
    if (scrollY > 0) {
      try {
        const raw = sessionStorage.getItem(SESSION_KEY);
        if (!raw) {
          capturePosition(null);
        }
      } catch (e) {}
    }
  });

  // 2. Restore scroll position on page load / reload / redirect
  function restorePosition() {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return;

      const data = JSON.parse(raw);
      const now = Date.now();

      // Expire if older than 30 seconds
      if (!data || typeof data.y !== 'number' || (now - data.timestamp) > 30000) {
        sessionStorage.removeItem(SESSION_KEY);
        return;
      }

      // Check path matching (same page or redirect back to dashboard/shops)
      const currentPath = window.location.pathname;
      const isSamePath = (data.path === currentPath);
      const isRelatedPath = (data.path && (currentPath.includes(data.path) || data.path.includes(currentPath)));

      if (!isSamePath && !isRelatedPath) {
        sessionStorage.removeItem(SESSION_KEY);
        return;
      }

      // Prevent browser default reset to (0,0)
      if ('scrollRestoration' in history) {
        history.scrollRestoration = 'manual';
      }

      const targetY = data.y;
      const targetX = data.x || 0;

      // Temporarily disable smooth scroll so browser restores coordinates instantly
      document.documentElement.classList.add('disable-smooth-scroll');

      function performScroll() {
        const maxScrollY = Math.max(
          0,
          document.documentElement.scrollHeight - window.innerHeight,
          document.body.scrollHeight - window.innerHeight
        );
        const clampedY = Math.min(targetY, maxScrollY);

        window.scrollTo({
          top: clampedY,
          left: targetX,
          behavior: 'instant'
        });
      }

      // Execute immediately and across multiple render frames to counter layout reflows
      performScroll();
      requestAnimationFrame(performScroll);
      setTimeout(performScroll, 30);
      setTimeout(performScroll, 100);
      setTimeout(performScroll, 250);
      setTimeout(performScroll, 450);

      // Re-enable smooth scroll and reset storage after restoration window
      setTimeout(() => {
        document.documentElement.classList.remove('disable-smooth-scroll');
        sessionStorage.removeItem(SESSION_KEY);
        if ('scrollRestoration' in history) {
          history.scrollRestoration = 'auto';
        }
      }, 700);
    } catch (err) {
      console.warn('Ente Naadu scroll restoration:', err);
    }
  }

  // Attempt restoration
  restorePosition();
  window.addEventListener('load', restorePosition);
}

/**
 * 7. Double-Submit Prevention for Forms
 * Protects against duplicate POST requests while preserving compact action button layouts
 */
function initDoubleSubmitPrevention() {
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    form.addEventListener('submit', (e) => {
      const submitBtn = e.submitter || form.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.dataset.submitting) {
        submitBtn.dataset.submitting = 'true';
        submitBtn.classList.add('opacity-75', 'cursor-not-allowed');
        const originalText = submitBtn.innerHTML;

        const isCompact = submitBtn.offsetWidth < 70 || submitBtn.textContent.trim().length <= 3;
        if (isCompact) {
          submitBtn.innerHTML = `
            <svg class="animate-spin h-3.5 w-3.5 inline-block text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          `;
        } else {
          submitBtn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 inline-block text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            ദയവായി കാത്തിരിക്കൂ...
          `;
        }

        // Fallback restoration in case of client-side abort
        setTimeout(() => {
          submitBtn.dataset.submitting = '';
          submitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
          submitBtn.innerHTML = originalText;
        }, 8000);
      }
    });
  });
}

/**
 * 8. Dynamic Cascading Dropdowns for Location (State -> District -> Panchayat / Area)
 * Instant, client-side, zero latency
 */
const KERALA_DISTRICTS = [
  "തിരുവനന്തപുരം (Thiruvananthapuram)",
  "കൊല്ലം (Kollam)",
  "പത്തനംതിട്ട (Pathanamthitta)",
  "ആലപ്പുഴ (Alappuzha)",
  "കോട്ടയം (Kottayam)",
  "ഇടുക്കി (Idukki)",
  "എറണാകുളം (Ernakulam)",
  "തൃശൂർ (Thrissur)",
  "പാലക്കാട് (Palakkad)",
  "മലപ്പുറം (Malappuram)",
  "കോഴിക്കോട് (Kozhikode)",
  "വയനാട് (Wayanad)",
  "കണ്ണൂർ (Kannur)",
  "കാസർഗോഡ് (Kasaragod)"
];

const KERALA_PANCHAYATS_BY_DISTRICT = {
  "തിരുവനന്തപുരം": [
    "വെള്ളനാട് (Vellanad)", "അരുവിക്കര (Aruvikkara)", "നെടുമങ്ങാട് (Nedumangad)", "കാട്ടാക്കട (Kattakada)",
    "നെയ്യാറ്റിൻകര (Neyyattinkara)", "വർക്കല (Varkala)", "ആറ്റിങ്ങൽ (Attingal)", "ചിറയിൻകീഴ് (Chirayinkeezhu)",
    "കിളിമാനൂർ (Kilimanoor)", "വിളപ്പിൽ (Vilappil)", "വിളവൂർക്കൽ (Vilavoorkal)", "മലയിൻകീഴ് (Malayinkeezhu)",
    "പോത്തൻകോട് (Pothencode)", "മംഗലപുരം (Mangalapuram)", "വെമ്പായം (Vembayam)", "കഴക്കൂട്ടം (Kazhakkoottam)",
    "നേമം (Nemom)", "ബാലരാമപുരം (Balaramapuram)", "കാരോട് (Karode)", "പാറശ്ശാല (Parassala)", "വെള്ളറട (Vellarada)"
  ],
  "കൊല്ലം": [
    "കൊട്ടാരക്കര (Kottarakkara)", "പുനലൂർ (Punalur)", "കരുനാഗപ്പള്ളി (Karunagappally)", "പരവൂർ (Paravoor)",
    "ചാത്തന്നൂർ (Chathannoor)", "അഞ്ചൽ (Anchal)", "കുണ്ടറ (Kundara)", "ശാസ്താംകോട്ട (Sasthamkotta)",
    "പത്തനാപുരം (Pathanapuram)", "ഓച്ചിറ (Oachira)", "ചവറ (Chavara)", "കടയ്ക്കൽ (Kadakkal)", "മയ്യനാട് (Mayyanad)"
  ],
  "പത്തനംതിട്ട": [
    "തിരുവല്ല (Thiruvalla)", "അടൂർ (Adoor)", "പന്തളം (Pandalam)", "റാന്നി (Ranni)",
    "കോഴഞ്ചേരി (Kozhencherry)", "കോന്നി (Konni)", "മല്ലപ്പള്ളി (Mallappally)", "ഏനാത്ത് (Enathu)", "ആറന്മുള (Aranmula)"
  ],
  "ആലപ്പുഴ": [
    "ചേർത്തല (Cherthala)", "കായംകുളം (Kayamkulam)", "മാവേലിക്കര (Mavelikkara)", "ചെങ്ങന്നൂർ (Chengannur)",
    "ഹരിപ്പാട് (Haripad)", "അമ്പലപ്പുഴ (Ambalappuzha)", "കുട്ടനാട് (Kuttanad)", "മാരാരിക്കുളം (Mararikulam)",
    "തുറവൂർ (Thuravoor)", "അരൂർ (Aroor)"
  ],
  "കോട്ടയം": [
    "പാലാ (Pala)", "ചങ്ങനാശ്ശേരി (Changanassery)", "കാഞ്ഞിരപ്പള്ളി (Kanjirappally)", "വൈക്കം (Vaikom)",
    "ഈരാറ്റുപേട്ട (Erattupetta)", "ഏറ്റുമാനൂർ (Ettumanoor)", "പുതുപ്പള്ളി (Puthuppally)", "കടുത്തുരുത്തി (Kaduthuruthy)",
    "പാമ്പാടി (Pampady)"
  ],
  "ഇടുക്കി": [
    "തൊടുപുഴ (Thodupuzha)", "കട്ടപ്പന (Kattappana)", "അടിമാലി (Adimali)", "മൂന്നാർ (Munnar)",
    "നെടുങ്കണ്ടം (Nedumkandam)", "പീരുമേട് (Peerumedu)", "വണ്ടിപ്പെരിയാർ (Vandiperiyar)", "കുമളി (Kumily)"
  ],
  "എറണാകുളം": [
    "ആലുവ (Aluva)", "അങ്കമാലി (Angamaly)", "പെരുമ്പാവൂർ (Perumbavoor)", "തൃപ്പൂണിത്തുറ (Tripunithura)",
    "കളമശ്ശേരി (Kalamassery)", "മൂവാറ്റുപുഴ (Muvattupuzha)", "കോതമംഗലം (Kothamangalam)", "പിറവം (Piravom)",
    "കൂത്താട്ടുകുളം (Koothattukulam)", "ചോറ്റാനിക്കര (Chottanikkara)", "വടക്കേക്കര (Vadakkekkara)", "പറവൂർ (Paravur)"
  ],
  "തൃശൂർ": [
    "ചാലക്കുടി (Chalakudy)", "കൊടുങ്ങല്ലൂർ (Kodungallur)", "കുന്നംകുളം (Kunnamkulam)", "ഗുരുവായൂർ (Guruvayur)",
    "ഇരിഞ്ഞാലക്കുട (Irinjalakuda)", "വടക്കാഞ്ചേരി (Wadakkanchery)", "ചേർപ്പ് (Cherpu)", "ഒല്ലൂർ (Ollur)",
    "പുതുക്കാട് (Puthukkad)", "മാള (Mala)", "തൃപ്രയാർ (Thriprayar)"
  ],
  "പാലക്കാട്": [
    "ചിറ്റൂർ (Chittur)", "ഒറ്റപ്പാലം (Ottapalam)", "ഷൊർണ്ണൂർ (Shoranur)", "മണ്ണാർക്കാട് (Mannarkkad)",
    "പട്ടാമ്പി (Pattambi)", "ചെർപ്പുളശ്ശേരി (Cherpulassery)", "ആലത്തൂർ (Alathur)", "കൊല്ലങ്കോട് (Kollengode)",
    "വടക്കഞ്ചേരി (Vadakkencherry)"
  ],
  "മലപ്പുറം": [
    "മഞ്ചേരി (Manjeri)", "തിരൂർ (Tirur)", "പൊന്നാനി (Ponnani)", "പെരിന്തൽമണ്ണ (Perinthalmanna)",
    "കോട്ടക്കൽ (Kottakkal)", "നിലമ്പൂർ (Nilambur)", "കൊണ്ടോട്ടി (Kondotty)", "താനൂർ (Tanur)",
    "വളാഞ്ചേരി (Valanchery)", "പരപ്പനങ്ങാടി (Parappanangadi)", "വേങ്ങര (Vengara)"
  ],
  "കോഴിക്കോട്": [
    "വടകര (Vadakara)", "കൊയിലാണ്ടി (Koyilandy)", "താമരശ്ശേരി (Thamarassery)", "കൊടുവള്ളി (Koduvally)",
    "ബാലുശ്ശേരി (Balussery)", "മുക്കം (Mukkam)", "ഫറോക്ക് (Feroke)", "രാമനാട്ടുകര (Ramanattukara)",
    "പേരാമ്പ്ര (Perambra)", "കുന്നമംഗലം (Kunnamangalam)", "നാദാപുരം (Nadapuram)"
  ],
  "വയനാട്": [
    "കൽപ്പറ്റ (Kalpetta)", "സുൽത്താൻ ബത്തേരി (Sultan Bathery)", "മാനന്തവാടി (Mananthavady)",
    "മേപ്പാടി (Meppadi)", "വൈത്തിരി (Vythiri)", "പുൽപ്പള്ളി (Pulpally)", "പനമരം (Panamaram)"
  ],
  "കണ്ണൂർ": [
    "തലശ്ശേരി (Thalassery)", "പയ്യന്നൂർ (Payyanur)", "തളിപ്പറമ്പ് (Taliparamba)", "കൂത്തുപറമ്പ് (Kuthuparamba)",
    "ഇരിട്ടി (Iritty)", "മട്ടന്നൂർ (Mattannur)", "പാനൂർ (Panoor)", "ശ്രീകണ്ഠപുരം (Sreekandapuram)", "പേരാവൂർ (Peravoor)"
  ],
  "കാസർഗോഡ്": [
    "കാഞ്ഞങ്ങാട് (Kanhangad)", "നീലേശ്വരം (Nileshwaram)", "ഉപ്പള (Uppala)", "മഞ്ചേശ്വരം (Manjeshwaram)",
    "ചെറുവത്തൂർ (Cheruvathur)", "വെള്ളരിക്കുണ്ട് (Vellarikundu)", "തൃക്കരിപ്പൂർ (Trikaripur)"
  ]
};

function getDbAreas() {
  try {
    const el = document.getElementById('dbAreasData');
    if (el && el.textContent) {
      return JSON.parse(el.textContent);
    }
  } catch (e) {
    console.warn('Could not parse dbAreasData', e);
  }
  return [];
}

function initLocationCascading() {
  setupCascadingPair('userRegState', 'userRegDistrict', 'userRegPanchayat', 'userRegCustomPanchayat', 'userRegAreaId');
  setupCascadingPair('shopRegState', 'shopRegDistrict', 'shopRegPanchayat', 'shopRegCustomPanchayat', 'shopRegAreaId');
}

function setupCascadingPair(stateId, districtId, panchayatId, customPanchayatId, areaIdInput) {
  const stateSelect = document.getElementById(stateId);
  const districtSelect = document.getElementById(districtId);
  const panchayatSelect = document.getElementById(panchayatId);
  const customInput = document.getElementById(customPanchayatId);
  const hiddenAreaId = document.getElementById(areaIdInput);

  if (!stateSelect || !districtSelect || !panchayatSelect) return;

  const dbAreas = getDbAreas();

  function populateDistricts() {
    const stateVal = stateSelect.value;
    districtSelect.innerHTML = '<option value="">-- ജില്ല തിരഞ്ഞെടുക്കുക --</option>';
    panchayatSelect.innerHTML = '<option value="">-- ആദ്യം ജില്ല തിരഞ്ഞെടുക്കൂ --</option>';
    if (customInput) customInput.classList.add('hidden');
    if (hiddenAreaId) hiddenAreaId.value = '';

    if (stateVal === 'Kerala' || stateVal === 'കേരളം') {
      KERALA_DISTRICTS.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        districtSelect.appendChild(opt);
      });
    } else {
      // General district option for other states
      const opt = document.createElement('option');
      opt.value = 'General';
      opt.textContent = 'ജനറൽ ഡിസ്ട്രിക്റ്റ് (General)';
      districtSelect.appendChild(opt);
    }
  }

  function populatePanchayats() {
    const districtVal = districtSelect.value;
    panchayatSelect.innerHTML = '<option value="">-- പഞ്ചായത്ത് / പ്രദേശം തിരഞ്ഞെടുക്കുക --</option>';
    if (customInput) customInput.classList.add('hidden');
    if (hiddenAreaId) hiddenAreaId.value = '';

    if (!districtVal) {
      panchayatSelect.innerHTML = '<option value="">-- ആദ്യം ജില്ല തിരഞ്ഞെടുക്കൂ --</option>';
      return;
    }

    // Identify matching district key
    let matchedKey = null;
    for (const key of Object.keys(KERALA_PANCHAYATS_BY_DISTRICT)) {
      if (districtVal.includes(key)) {
        matchedKey = key;
        break;
      }
    }

    // Add matching DB areas first (if any)
    const addedNames = new Set();
    dbAreas.forEach(a => {
      if (a.district && (districtVal.includes(a.district) || a.district.includes(matchedKey || ''))) {
        const opt = document.createElement('option');
        opt.value = a.name;
        opt.dataset.areaId = a.id;
        opt.textContent = `${a.name} ⭐ (രജിസ്റ്റർ ചെയ്ത പ്രദേശം)`;
        panchayatSelect.appendChild(opt);
        addedNames.add(a.name.toLowerCase());
      }
    });

    // Add Panchayats for this district from dataset
    if (matchedKey && KERALA_PANCHAYATS_BY_DISTRICT[matchedKey]) {
      KERALA_PANCHAYATS_BY_DISTRICT[matchedKey].forEach(p => {
        const cleanName = p.split(' (')[0].trim().toLowerCase();
        if (!addedNames.has(cleanName)) {
          const opt = document.createElement('option');
          opt.value = p;
          opt.textContent = p;
          panchayatSelect.appendChild(opt);
        }
      });
    }

    // Always append "Other / Custom" option at the end
    const otherOpt = document.createElement('option');
    otherOpt.value = '__custom__';
    otherOpt.textContent = '➕ മറ്റുള്ളവ (പഞ്ചായത്തിന്റെ പേര് ടൈപ്പ് ചെയ്യാം)';
    panchayatSelect.appendChild(otherOpt);
  }

  stateSelect.addEventListener('change', () => {
    populateDistricts();
  });

  districtSelect.addEventListener('change', () => {
    populatePanchayats();
  });

  panchayatSelect.addEventListener('change', () => {
    const selectedOpt = panchayatSelect.options[panchayatSelect.selectedIndex];
    if (panchayatSelect.value === '__custom__') {
      if (customInput) {
        customInput.classList.remove('hidden');
        customInput.focus();
      }
      if (hiddenAreaId) hiddenAreaId.value = '';
    } else {
      if (customInput) {
        customInput.classList.add('hidden');
        customInput.value = '';
      }
      if (hiddenAreaId) {
        hiddenAreaId.value = selectedOpt && selectedOpt.dataset.areaId ? selectedOpt.dataset.areaId : '';
      }
    }
  });

  // Initial population for default state (Kerala)
  populateDistricts();
}

