/**
 * index.js
 *
 * Handles client-side interactions for the MovieRecApp:
 * - CSRF token retrieval
 * - AJAX toggling of favorites
 * - Auto-submit of model ratings
 * - Expand/collapse movie details
 * - Initialization of Select2 for multi- and single-select filters
 * - Setup of noUiSlider for year and rating range filters
 * - AJAX "Load More" pagination for recommendations
 */

// Retrieve CSRF token from meta tag for secure AJAX requests
const csrfToken = document
  .querySelector('meta[name="csrf-token"]')
  .getAttribute('content');

/**
 * toggleFavorite
 * Send an AJAX POST to toggle favorite status for a given movie.
 * Updates button text and data attribute on success.
 */
async function toggleFavorite(btn) {
  const mid   = btn.dataset.mid;
  const faved = btn.dataset.faved === '1';

  const resp = await fetch(`/favorite/${mid}`, {
    method: 'POST',
    headers: {
      'X-CSRFToken':     csrfToken,
      'X-Requested-With':'XMLHttpRequest'
    },
    credentials: 'same-origin'
  });

  if (resp.status === 204) {
    // Flip button label and state
    btn.textContent        = faved ? 'Add Favorite'    : 'Remove Favorite';
    btn.dataset.faved      = faved ? '0'                : '1';
  } else {
    console.error('Favorite toggle failed', resp);
  }
}

/**
 * toggleDetails
 * Expand or collapse extra movie details panel.
 */
function toggleDetails(detailsId, btn) {
  const panel    = document.getElementById(detailsId);
  const isHidden = panel.classList.toggle('hidden');
  btn.textContent = isHidden ? 'More Info' : 'Less Info';
}

/**
 * Auto-submit model-rating form when a star is selected.
 */
document.body.addEventListener('change', async e => {
  const input = e.target;

  if (input.name !== 'model_rating') return;
  
  const form = input.closest('.model-rating-form');
  const url  = form.action;
  const data = new URLSearchParams(new FormData(form));
  
  const resp = await fetch(url, {
    method:      'POST',
    body:        data,
    headers: {
      'X-CSRFToken':      csrfToken,
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin'
  });

  if (resp.status === 204) {
    console.log(`Rated movie ${data.get('movie_id')} → ${data.get('model_rating')}`);
  } else {
    console.error('Model-rating failed', resp);
  }
});

/**
 * Initialize Select2, sliders, and load-more button handlers once DOM is ready.
 */
window.addEventListener('DOMContentLoaded', () => {
  // Multi-select AJAX-powered filters for genre, studio, director
  ['genre','studio','director'].forEach(id => {
    const el = document.getElementById(id);
    if (el && window.jQuery && jQuery.fn.select2) {
      $(el).select2({
        multiple:        true,
        tags:            false,
        tokenSeparators: [','],
        placeholder:     id.charAt(0).toUpperCase() + id.slice(1),
        ajax: {
          url: el.dataset.ajaxUrl,
          dataType: 'json',
          delay:    250,
          data:     params => ({ q: params.term }),
          processResults: data => ({ results: data })
        },
        minimumInputLength: 2,
        allowClear:         true
      });
    }
  });    

  // Multi-select AJAX-powered filters for producer and cast member
  ['producer','cast_member'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && window.jQuery && jQuery.fn.select2) {
      $(sel).select2({
        tags: false,
        multiple: true,
        tokenSeparators: [','],
        placeholder: id === 'producer'
          ? 'Start typing to add/select…'
          : 'Start typing to add/select…',
        allowClear: true,
        ajax: {
          url: sel.dataset.ajaxUrl,
          dataType: 'json',
          delay: 250,
          data: params => ({ q: params.term }),
          processResults: data => ({ results: data })
        },
        minimumInputLength: 2
      });
    }
  });  

  // Year range slider setup using noUiSlider
  const yearSlider = document.getElementById('year-slider');
  if (yearSlider && typeof noUiSlider !== 'undefined') {
    const fromInput = document.getElementById('year_from');
    const toInput   = document.getElementById('year_to');
    const minY      = parseInt(fromInput.value, 10);
    const maxY      = parseInt(toInput.value, 10);

    noUiSlider.create(yearSlider, {
      start:   [minY, maxY],
      connect: true,
      range:   { min: minY, max: maxY },
      step:    1,
      tooltips: [
        { to: v => Math.round(v), from: v => Number(v) },
        { to: v => Math.round(v), from: v => Number(v) }
      ],
      format:  { to: v => Math.round(v), from: v => Number(v) }
    })
  }

  // Rating range slider setup
  const ratingSlider = document.getElementById('rating-slider');
  if (ratingSlider && typeof noUiSlider !== 'undefined') {
    const fromInput = document.getElementById('rating_from');
    const toInput   = document.getElementById('rating_to');
    const minR      = parseFloat(fromInput.value);
    const maxR      = parseFloat(toInput.value);

    noUiSlider.create(ratingSlider, {
      start:   [minR, maxR],
      connect: true,
      range:   { min: minR, max: maxR },
      step:    0.1,
      tooltips: [
        { to: v => parseFloat(v).toFixed(1), from: v => Number(v) },
        { to: v => parseFloat(v).toFixed(1), from: v => Number(v) }
      ],
      format:  { to: v => parseFloat(v).toFixed(1), from: v => Number(v) }
    })
  }
});

/**
 * Handle "Load More" button for AJAX pagination of recommendations.
 */
document.body.addEventListener('click', async e => {
    const btn = e.target.closest('#load-more');
    if (!btn) return;
  
    let offset = btn.dataset.offset;
    const limit = 5;
  
    const params = new URLSearchParams(window.location.search);
    params.set('offset', offset);
    params.set('limit', limit);
  
    const resp = await fetch(`/recommend?${params}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    const { movies, next_offset, has_more } = await resp.json();
    const container = document.getElementById('rec-container');
  
    // Append each new movie block to container
    movies.forEach(m => {
      const html = `
        <div class="flex bg-gray-100 dark:bg-gray-800 rounded shadow overflow-hidden mb-6">
          <img src="${m.poster_url}" alt="${m.title} poster" class="w-1/3 object-cover">
          <div class="p-6 flex-1 flex flex-col justify-between">
            <div>
              <div class="flex items-baseline justify-between mb-2">
                <h2 class="text-xl font-semibold">${m.title}</h2>
                <div class="text-sm text-gray-600 dark:text-gray-400 space-x-4">
                  <span>Similarity: ${m.sim.toFixed(2)}</span>
                  <span>Rating: ${parseFloat(m.avg_rating).toFixed(1)}</span>
                </div>
              </div>
              <p class="mb-4">${m.description}</p>
              <form action="/rate_model" method="post" class="model-rating-form mb-4 text-sm">
                <input type="hidden" name="csrf_token" value="${csrfToken}">
                <input type="hidden" name="movie_id"   value="${m.movie_id}">
                <div class="font-medium mb-1">Rate performance of recommendation</div>
                <div class="star-rating">
                  ${[...Array(10)].map((_,i) => {
                    const val = 10 - i;
                    return `
                      <input type="radio"
                             id="star-${m.movie_id}-${val}"
                             name="model_rating"
                             value="${val}">
                      <label for="star-${m.movie_id}-${val}"></label>
                    `;
                  }).join('')}
                </div>
              </form>
              <button type="button"
                      class="text-blue-500 hover:underline mb-4"
                      onclick="toggleDetails('det-${m.movie_id}', this)">
                More Info
              </button>
              <div id="det-${m.movie_id}"
                   class="hidden text-sm space-y-1 text-gray-700 dark:text-gray-300 mb-4">
                <p><strong>Year:</strong> ${m.year}</p>
                <p><strong>Genre:</strong> ${m.genres.join(', ')}</p>
                <p><strong>Studios:</strong> ${m.studios.join(', ')}</p>
                <p><strong>Director:</strong> ${m.director}</p>
                <p><strong>Producers:</strong> ${m.producers.join(', ')}</p>
                <p><strong>Cast:</strong> ${m.cast.join(', ')}</p>
                <p><strong>Duration:</strong> ${m.duration} min</p>
                <a href="${m.page_url}" target="_blank" class="text-blue-500 hover:underline">
                  View on site
                </a>
              </div>
            </div>
            <button type="button"
                    class="text-red-500 hover:underline"
                    data-mid="${m.movie_id}"
                    data-faved="${m.faved?1:0}"
                    onclick="toggleFavorite(this)">
              ${m.faved ? 'Remove Favorite' : 'Add Favorite'}
            </button>
          </div>
        </div>`;
      container.insertAdjacentHTML('beforeend', html);
    });
  
    if (has_more) {
      btn.dataset.offset = next_offset;
    } else {
      btn.remove();
    }
});
  