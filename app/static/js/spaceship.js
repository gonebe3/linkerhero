// Spaceship UI JavaScript
document.addEventListener('DOMContentLoaded', function() {
    
    // Navigation scroll effect
    const nav = document.querySelector('.nav');
    let lastScrollY = window.scrollY;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
        lastScrollY = window.scrollY;
    });

    // Particle system
    function createParticles() {
        const particlesContainer = document.createElement('div');
        particlesContainer.className = 'particles';
        document.body.appendChild(particlesContainer);

        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 6 + 's';
            particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
            particlesContainer.appendChild(particle);
        }
    }

    // Interactive button effects
    function addButtonEffects() {
        const buttons = document.querySelectorAll('.btn');
        
        buttons.forEach(button => {
            button.classList.add('interactive-btn');
            
            button.addEventListener('mouseenter', function(e) {
                this.style.transform = 'translateY(-3px) scale(1.05)';
            });
            
            button.addEventListener('mouseleave', function(e) {
                this.style.transform = 'translateY(0) scale(1)';
            });
            
            button.addEventListener('mousedown', function(e) {
                this.style.transform = 'translateY(-1px) scale(1.02)';
            });
            
            button.addEventListener('mouseup', function(e) {
                this.style.transform = 'translateY(-3px) scale(1.05)';
            });
        });
    }

    // Card hover effects
    function addCardEffects() {
        const cards = document.querySelectorAll('.card, .list-item');
        
        cards.forEach(card => {
            card.addEventListener('mouseenter', function(e) {
                this.style.transform = 'translateY(-8px) rotateX(5deg)';
                this.style.boxShadow = '0 40px 100px rgba(0, 0, 0, 0.5)';
            });
            
            card.addEventListener('mouseleave', function(e) {
                this.style.transform = 'translateY(0) rotateX(0deg)';
                this.style.boxShadow = '';
            });
        });
    }

    // Form input effects
    function addFormEffects() {
        const inputs = document.querySelectorAll('.form-input, .form-select, .form-textarea');
        
        inputs.forEach(input => {
            input.addEventListener('focus', function(e) {
                this.parentElement.style.transform = 'scale(1.02)';
                this.style.boxShadow = '0 0 0 4px rgba(255, 111, 78, 0.3), 0 10px 30px rgba(255, 111, 78, 0.2)';
            });
            
            input.addEventListener('blur', function(e) {
                this.parentElement.style.transform = 'scale(1)';
                this.style.boxShadow = '';
            });
        });
    }

    // Smooth scrolling for navigation links
    function addSmoothScrolling() {
        const navLinks = document.querySelectorAll('.nav-links a[href^="#"]');
        
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetId = this.getAttribute('href');
                const targetSection = document.querySelector(targetId);
                
                if (targetSection) {
                    targetSection.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    // Loading animation for HTMX requests
    function addLoadingAnimations() {
        document.addEventListener('htmx:beforeRequest', function(evt) {
            const target = evt.target;
            const button = target.querySelector('button[type="submit"]');
            
            if (button) {
                button.innerHTML = '<span class="spinner"></span> Generating...';
                button.disabled = true;
                button.classList.add('loading');
            }
        });
        
        document.addEventListener('htmx:afterRequest', function(evt) {
            const target = evt.target;
            const button = target.querySelector('button[type="submit"]');
            
            if (button) {
                button.innerHTML = '✨ Generate Posts';
                button.disabled = false;
                button.classList.remove('loading');
            }
        });
    }

    // Typewriter effect for hero text
    function typewriterEffect() {
        const heroTitle = document.querySelector('.hero h1');
        if (!heroTitle) return;
        
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        heroTitle.style.opacity = '1';
        
        let i = 0;
        const timer = setInterval(() => {
            if (i < text.length) {
                heroTitle.textContent += text.charAt(i);
                i++;
            } else {
                clearInterval(timer);
            }
        }, 100);
    }

    // Parallax effect for hero circles
    function addParallaxEffect() {
        const heroCircles = document.querySelectorAll('.hero-circle');
        
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const rate = scrolled * -0.5;
            
            heroCircles.forEach((circle, index) => {
                const speed = (index + 1) * 0.3;
                circle.style.transform = `translateY(${rate * speed}px) rotate(${scrolled * 0.1}deg)`;
            });
        });
    }

    // Copy to clipboard functionality
    function addCopyButtons() {
        const generatedContent = document.querySelectorAll('.generated-content');
        
        generatedContent.forEach(content => {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'btn btn-copy';
            copyBtn.innerHTML = '📋 Copy';
            copyBtn.style.position = 'absolute';
            copyBtn.style.top = '1rem';
            copyBtn.style.right = '1rem';
            copyBtn.style.padding = '0.5rem 1rem';
            copyBtn.style.fontSize = '0.9rem';
            
            content.style.position = 'relative';
            content.appendChild(copyBtn);
            
            copyBtn.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(content.textContent);
                    copyBtn.innerHTML = '✅ Copied!';
                    copyBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                    
                    setTimeout(() => {
                        copyBtn.innerHTML = '📋 Copy';
                        copyBtn.style.background = '';
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy text: ', err);
                }
            });
        });
    }

    // Score animation
    function animateScores() {
        const scoreValues = document.querySelectorAll('.score-item-value');
        
        scoreValues.forEach(score => {
            const finalValue = parseInt(score.textContent);
            let currentValue = 0;
            score.textContent = '0';
            
            const increment = finalValue / 50;
            const timer = setInterval(() => {
                currentValue += increment;
                if (currentValue >= finalValue) {
                    score.textContent = finalValue;
                    clearInterval(timer);
                } else {
                    score.textContent = Math.floor(currentValue);
                }
            }, 30);
        });
    }

    // Initialize all effects
    function init() {
        createParticles();
        addButtonEffects();
        addCardEffects();
        addFormEffects();
        addSmoothScrolling();
        addLoadingAnimations();
        addParallaxEffect();
        
        // Delayed effects
        setTimeout(() => {
            typewriterEffect();
        }, 500);
        
        // Observer for animations when elements come into view
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.animation = 'fadeInUp 0.8s ease-out forwards';
                    
                    // Animate scores when they come into view
                    if (entry.target.classList.contains('score-breakdown')) {
                        animateScores();
                    }
                    
                    // Add copy buttons to generated content
                    if (entry.target.classList.contains('generated-content')) {
                        addCopyButtons();
                    }
                }
            });
        }, {
            threshold: 0.1
        });
        
        // Observe elements for animations
        document.querySelectorAll('.card, .list-item, .score-breakdown, .generated-content').forEach(el => {
            observer.observe(el);
        });
    }

    // Start the magic
    init();
    
    // Parallax effect for all floating blocks
    function addParallaxEffects() {
        // Disable parallax on News Feed page where it is distracting
        if (window.location && window.location.pathname && window.location.pathname.startsWith('/news')) {
            return;
        }
        const hero = document.querySelector('.hero');
        const sections = document.querySelectorAll('.section');
        
        const onScroll = () => {
            const scrolled = window.pageYOffset;
            const viewportHeight = window.innerHeight;
            
            // Hero parallax with fading and right-only movement
            if (hero) {
                // If at/near top, ensure fully opaque and reset transform
                if (scrolled <= 10) {
                    hero.style.opacity = '1';
                    hero.style.transform = 'translate(0px, 0px) translateZ(0)';
                } else {
                    // Fade based purely on scroll distance from top (not element metrics)
                    const fadeDistance = viewportHeight * 0.6; // distance over which to fade
                    const fadeProgress = Math.min(1, scrolled / fadeDistance);
                    const opacity = 1 - (fadeProgress * 0.8); // fade to 0.2 min opacity

                    const rightOffset = scrolled * 0.2; // Move to the right only
                    hero.style.transform = `translate(${rightOffset}px, 0px) translateZ(0)`;
                    hero.style.opacity = String(opacity);
                }
            }
            
            // If near the very top, fully reset all sections
            if (scrolled <= 10) {
                sections.forEach((section) => {
                    section.style.transform = 'translate(0px, 0px) translateZ(0)';
                    section.style.opacity = '1';
                });
                return;
            }

            // Section parallax with directional movement
            sections.forEach((section, index) => {
                const rect = section.getBoundingClientRect();
                const elementTop = rect.top + scrolled;
                const elementHeight = rect.height;
                
                // Calculate if element is in viewport
                if (rect.top < viewportHeight * 1.5 && rect.bottom > -viewportHeight * 0.5) {
                    const centerY = elementTop + elementHeight / 2;
                    const distanceFromCenter = scrolled + viewportHeight / 2 - centerY;
                    const normalizedDistance = distanceFromCenter / viewportHeight;
                    
                    // Different movement for different sections
                    let xOffset = 0;
                    let yOffset = 0;
                    
                    if (section.classList.contains('parallax-left')) {
                        // Move left sections to the left when scrolling
                        xOffset = normalizedDistance * -30;
                        yOffset = 0; // lock vertical drift for alignment
                    } else if (section.classList.contains('parallax-right')) {
                        // Move right sections to the right when scrolling
                        xOffset = normalizedDistance * 30;
                        yOffset = 0; // lock vertical drift for alignment
                    } else {
                        // Default vertical parallax
                        yOffset = 0; // avoid vertical drift in default
                    }
                    
                    // Calculate opacity for fading effect
                    const fadeDistance = Math.abs(normalizedDistance);
                    const opacity = Math.max(0.7, 1 - fadeDistance * 0.5); // raise min opacity to avoid dim look when returning
                    
                    section.style.transform = `translate(${xOffset}px, ${yOffset}px) translateZ(0)`;
                    section.style.opacity = opacity;
                }
            });
        };
        window.addEventListener('scroll', onScroll);
        // Run once to ensure correct initial state
        onScroll();
    }
    
    // Add parallax effects
    addParallaxEffects();
});

// Scroll to next section function
function scrollToSection() {
    const firstSection = document.querySelector('.container .section');
    if (firstSection) {
        firstSection.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Additional utility functions
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 2rem;
        background: ${type === 'success' ? 'rgba(34, 197, 94, 0.9)' : 'rgba(220, 38, 38, 0.9)'};
        color: white;
        border-radius: 10px;
        backdrop-filter: blur(10px);
        z-index: 9999;
        animation: slideInRight 0.5s ease-out;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.5s ease-in forwards';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 500);
    }, 3000);
}

// Add custom CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    @keyframes fadeInUp {
        from { transform: translateY(30px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
`;
document.head.appendChild(style);
