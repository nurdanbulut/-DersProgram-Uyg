class FlashAlert{
    constructor(text, type){
        const div = document.createElement('div');

        div.classList = `alert alert-${type}`;
    
        div.textContent = text;

        this.alert = div
    }

    show_alert(ms){
        const container = document.querySelector('.container-md');

        container.insertBefore(this.alert, container.firstChild);

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
        setTimeout(()=>{
            this.alert.remove();
        }, ms)
    }
}
