

$(function () {
  $('[data-toggle="tooltip"]').tooltip()
})

$('#myDropdown').on('show.bs.dropdown', function () {
  // do something…
  alert('hi')
})
