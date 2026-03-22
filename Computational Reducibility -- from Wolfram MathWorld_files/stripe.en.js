    window.addEventListener('DOMContentLoaded', function(){
		let render = `
    <div id="IPstripe-outer" class="generic">
        <a id="IPstripe-main" href="//www.wolfram.com/siteinfo/" data-walid="siteinfo-stripe-general">
            <span id="IPstripe-txt">Find out if you already have access to Wolfram tech through your&nbsp;organization</span>
        </a>
        <div class="IPstripe-close">&times;</div>
    </div>

`;
		let wrappers = ["IPstripe-wrap"];
		let onsite = false;
		let wrappersCount = wrappers.length;


		if(!isCookieSet()){
			let styles = document.createElement('link');
			styles.rel =  'stylesheet';
			styles.href = '//mathworld.wolfram.com/common/stripe/css/style.en.css';
			document.head.appendChild(styles);
			
			for (var i = 0; i < wrappersCount; i++) {
				let wrapper = document.getElementById(wrappers[i]);
				if(wrapper !== null){
					wrapper.insertAdjacentHTML('beforeend', render);
				}
			}

			window.addEventListener('click', closeClicked, false);

			document.body.classList.add('stripe');
			if(!onsite){
				document.body.classList.add('generic');
			}
		}

		function closeClicked(e){
			let target = e.target;
			if(target.classList.contains('IPstripe-close')){
				setCookie();
				document.body.classList.remove('stripe');
				for (var i = 0; i < wrappersCount; i++) {
					document.getElementById(wrappers[i]).innerHTML = '';
				}
			}
		}

		function isCookieSet(){
			if (document.cookie.indexOf('_site_stripe') > -1 ) {
				return true;
			}

			return false;
		}

		function setCookie(){
			let domainParts = location.host.split('.');
			if(domainParts.length > 2){
				domainParts = domainParts.slice(-2);
			}
			let domain = '.' + domainParts.join('.');

			let expire = new Date();
			expire.setMonth(expire.getMonth() + 1);
			document.cookie = '_site_stripe=1;' + 'domain=' + domain + ';path=/';
		}
	});
