// static/script.js

$(document).ready(function () {
    $('#searchInput').on('input', function () {
        search();
    });
});

function search() {
    var keyword = $('#searchInput').val();

    $.ajax({
        url: '/search',
        data: { keyword: keyword },
        success: function (data) {
            // Display search results in the same place as the candidate list
            $('#candidateList').html(data);
        }
    });
}
