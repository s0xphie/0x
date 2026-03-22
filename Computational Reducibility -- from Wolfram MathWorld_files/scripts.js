/* BRIEF DESCRIPTION OF SCRIPT'S PURPOSE.

   developer:   estevaot, yhechler
   requires:    
  ========================================================================== */
/* ==========================================================================
   Function for the left-side/header menu
   ========================================================================== */
window.addEventListener('DOMContentLoaded', (event) => {

    const searchField = document.getElementById('searchField');
	const searchFieldHome = document.getElementById('searchFieldHome');
	if (searchFieldHome) {
		searchFieldHome.focus();
	}
	if (searchField) {
        searchField.focus();
    }

    const leftSide = document.querySelector(".left-side");
    const openBtn = document.querySelector("#header-dropdown-menu");

    if (openBtn) {
        const dropdownCloseBtn = document.querySelector("#dropdown-topics-menu-close");

        if (dropdownCloseBtn) {

        	let distanceScrolled = 0;

            openBtn.addEventListener('click', function () {
            	distanceScrolled = window.scrollY;
                leftSide.classList.add("show-menu");
                const searchFieldMobile = document.getElementById('searchFieldMobile');
                if (searchFieldMobile) {
                    searchFieldMobile.focus({preventScroll: true});
                }
            });

            dropdownCloseBtn.addEventListener('click', function(){
            	if(leftSide!=undefined) {
            		leftSide.classList.remove("show-menu");	
            	}
            });

			let _checkScrollToCloseMenu = function(){
				if(leftSide != undefined && leftSide.classList.contains("show-menu") && Math.abs(window.scrollY-distanceScrolled) > 50) {
                 	leftSide.classList.remove("show-menu");
                }
			};
			
			//Set an event for resizing the window
			window.addEventListener('scroll', _checkScrollToCloseMenu);

            document.body.addEventListener('click', function (event) {
                const menuIcon = document.querySelector("#menu-icon");
                if (leftSide.classList.contains("show-menu") && !leftSide.contains(event.target) && event.target !== menuIcon) {
                    leftSide.classList.remove("show-menu");
                    const searchFieldMobile = document.getElementById('searchFieldMobile');
                    if (searchFieldMobile) {
                        searchFieldMobile.blur();
                    }
                }
            });

			leftSide.addEventListener('click', function (event) {
				if (event.target.id !== 'menu-icon') {
					event.stopPropagation();
				}
			});
        }
    }
});

/* =======
   Resize inline math in references to match surrounding text
   ======= */

document.addEventListener("DOMContentLoaded", function() {
  const images = document.querySelectorAll("cite .inlineformula");

  images.forEach(function(img) {
    // Get the original width and height of the image
    const currentWidth = img.offsetWidth;
    const currentHeight = img.offsetHeight;
    
    // Calculate new width and height (reduce by 20%)
    const newWidth = currentWidth * 0.8;
    const newHeight = currentHeight * 0.8;

    // Apply new dimensions to the image
    img.style.width = newWidth + "px";
    img.style.height = newHeight + "px";
  });
});


/* ==========================================================================
   Responsive tables
   ========================================================================== */
const responsiveTablesHeight = [...document.querySelectorAll('.table-responsive')].filter(x => x.clientHeight < x.scrollHeight)
if (responsiveTablesHeight != undefined) {
	responsiveTablesHeight.forEach(function(element) {
		element.classList.add('table-full-height');
	});
}
const responsiveTablesWidth = [...document.querySelectorAll('.table-responsive')].filter(x => x.clientWidth < x.scrollWidth)
if (responsiveTablesWidth != undefined) {
	responsiveTablesWidth.forEach(function(element) {
		element.classList.add('table-full-width');
	});
}
/* ==========================================================================
   Search animation
   ========================================================================== */
const header = document.querySelector("header");
const headerSearchForm = document.querySelector("header form");
const headerSearchBtn = document.querySelector("header #search .search-btn");
if (headerSearchBtn != undefined) {
	const headerSearchClose = document.querySelector("header #search-close");
	headerSearchBtn.addEventListener('click', function(e) {
		header.classList.add('openSearch');
		searchInput = document.getElementsByName('query')[0];
		if (searchInput != undefined) {
			searchInput.focus();
		} else {
			headerSearchForm.submit();
		}
	});
	headerSearchClose.addEventListener('click', function(e) {
		header.classList.remove('openSearch');
	});
}

function submitForm() {
	document.getElementById('search-mobile').submit();
}
/* ==========================================================================
   Show more/less breadcrumbs
   ========================================================================== */
const breadcrumbsNavs = document.querySelectorAll("#content nav.breadcrumbs");
if (breadcrumbsNavs != undefined) {
	breadcrumbsNavs.forEach(function(element) {
		breadcrumbs = element.querySelectorAll(".breadcrumb")
		if (breadcrumbs.length > 3) {
			// navBreadcrumbs  = element
			viewMoreBcrumbs = element.querySelector("a.show-more");
			viewLessBcrumbs = element.querySelector("a.show-less");
			if (viewMoreBcrumbs != undefined && viewLessBcrumbs != undefined) {
				viewMoreBcrumbs.classList.remove('display-n');
				viewMoreBcrumbs.addEventListener('click', function(e) {
					this.classList.add('display-n');
					this.parentElement.classList.add('open');
					this.nextElementSibling.classList.remove('display-n');
				});
				viewLessBcrumbs.addEventListener('click', function(e) {
					this.classList.add('display-n');
					this.parentElement.classList.remove('open');
					this.previousElementSibling.classList.remove('display-n');
				});
			}
		}
	})
}
/* ==========================================================================
   Auto populate Wolfram Alpha Pod
   ========================================================================== */
window.addEventListener('load', function() {
	var linktext = document.querySelectorAll('.try ul li a');
	if (typeof linktext != undefined && linktext[0] != undefined) {
		linktext = linktext[0].textContent;
		document.querySelectorAll('#WAwidget .WAwidget-wrapper form input')[0].value = linktext;
	}
});
/* ==========================================================================
   Swap images when you have a smaller image and you are 750 pixels wide
   ========================================================================== */
var elems = document.querySelectorAll('img.swappable');
elems.forEach(function(el, i) {
	if (el.getAttribute('data-src-small') !== null && el.getAttribute('data-src-small') !== '') {
		if (el.getAttribute('data-small') !== '' && el.getAttribute('data-small') !== null) {
			imgSwap(el);
		}
	}
});

function imgSwap(img) {
	swap(img);
	window.addEventListener('resize', function() {
		swap(img);
	}, false);

	function swap(img) {
		if (window.innerWidth < 750) {
			var src = img.getAttribute('data-src-small'),
				ext = src.split('.').pop(),
				w = img.getAttribute('data-small').split(' ')[0],
				h = img.getAttribute('data-small').split(' ')[1];
			if (src.indexOf('_400') > 0) {
				if (img.getAttribute('src') !== null && img.getAttribute('src') !== '') {
					img.setAttribute('height', h);
					img.setAttribute('src', src);
					img.setAttribute('width', w);
				}
			}
		} else {
			var src = img.getAttribute('data-src-default'),
				w = img.getAttribute('data-big').split(' ')[0],
				h = img.getAttribute('data-big').split(' ')[1];
			if (img.getAttribute('src') !== null && img.getAttribute('src') !== '') {
				img.setAttribute('height', h);
				img.setAttribute('width', w);
				img.setAttribute('src', src);
			}
		}
	}
}