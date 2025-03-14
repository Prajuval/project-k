// Load cart from localStorage
const savedCart = localStorage.getItem('cart');
if (savedCart) {
    const parsedCart = JSON.parse(savedCart);
    cart.items = parsedCart.items;
    cart.total = parsedCart.total;
    updateCart();
}

function checkout() {
    if (cart.items.length === 0) {
        alert('Your cart is empty!');
        return;
    }
    // Redirect to the checkout page so that the user can select booking date & time
    window.location.href = '/checkout';
}

// Update localStorage when cart changes
function updateCart() {
    // ...existing update code...
    
    // Save to localStorage
    localStorage.setItem('cart', JSON.stringify(cart));
}