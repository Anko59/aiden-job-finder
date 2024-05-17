
let totalTokensUsed = 0;
let totalPricePaid = 0;

function updateTokenCounter(tokensUsed) {
    totalTokensUsed = tokensUsed;
    $('#token-counter').text('MistralAI Total Tokens Used: ' + totalTokensUsed);
}

function updateTotalPriceCounter(tokensUsed) {
    let pricePaid = (tokensUsed / 1000) * 0.01;
    totalPricePaid += pricePaid;
    $('#total-price-counter').text('Total Price Paid: $' + totalPricePaid.toFixed(2));
}

export function updateCounters(tokensUsed) {
    updateTokenCounter(tokensUsed);
    updateTotalPriceCounter(tokensUsed);
}
